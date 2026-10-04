---
id: 0016-question-answering-flow
title: "ADR 0016: Question-answering flow"
sidebar_position: 16
description: How a question is classified, routed, answered from evidence and verified, with fixed replies for every other case.
---

# ADR 0016: Question-answering flow

## Status

Accepted, 2026-10-04.

## Context

Answers about Islam must come only from vetted evidence, never from the model's memory,
and questions the AI must not answer must reach specialists. Every answer is kept for
review and future fine-tuning.

## Decision

- **CrewAI 1.9.3**, documented structure: a Flow (`agents/flow.py`) and two crews with
  YAML agents and tasks (`agents/crews/classify_crew`, `agents/crews/answer_crew`).
- **Route**: classify (language, level A/B/C/D/out_of_scope, Arabic search query);
  out of scope → fixed refusal; level D (personal ruling) → fixed referral; else
  `search(k=8)`; best score below `LOW_THRESHOLD` → fixed abstain; else the evidence of
  the top `EVIDENCE_QUESTIONS` (3) questions goes to the writer, then the verifier.
- **Verifier with quotes**: it returns each kept sentence with an exact supporting quote;
  the code drops sentences whose quote (≥ 15 characters, normalized) is not in the
  evidence. A support check on 2026-10-04 found 3 unsupported claims out of 7 sentences
  with gpt-4o-mini as verifier and 1 out of 12 with gpt-4o, so `AISettings.verifier_model`
  is `gpt-4o` (writer and classifier stay on `chat_model`, gpt-4o-mini).
- **Entailment check**: after the quote check, ONE batched request to the verifier model
  judges every sentence–quote pair supported / not_supported (supported only if the quote
  alone states the claim, with nothing added); not_supported sentences are dropped and
  recorded. The writer is told to stay close to the evidence wording and avoid connectors
  such as "مما يدل على" or "rather than".
- **Language**: decided by script for Arabic (the classifier once labelled an English
  question "ar"); otherwise the classifier's label.
- **Decide** (code, not model): citations outside the evidence are stripped; no valid
  citation or coverage "none" → referral; "partial" → answer + fixed note; level C →
  answer + fixed notice. Fixed replies are translated (ar/en/fr), never generated.
- **Failures** of any step → fixed abstain; the error is saved with keys masked.
- **Records**: `qa.Question` (anonymous, owned by the default center), `qa.Interaction`
  (routing, retrieval, evidence, citations, decision, verdict, model, prompt version =
  hash of the YAML and output shapes, latency, tokens), `qa.HumanLabel`.
- **Operations**: CrewAI telemetry and tracing off; its first-run "view traces?" prompt is
  declined in `AgentsConfig.ready()`, before CrewAI is imported (it blocks a server); flow console panels suppressed; LLM
  calls time out after 60 s; worker-thread DB connections are closed.

## Consequences

- An answered question costs two calls over the full evidence (about 30,000 input tokens
  measured for #229), the verifier on gpt-4o.
- The quote check proves a quote exists, not that it entails the sentence; the remaining
  gap is measured by the 60-question evaluation (2026-10-06) and human labels.
- Handler methods must not share names with router labels (CrewAI loops otherwise).
