---
id: finetuning-dataset
title: Fine-tuning dataset
sidebar_position: 6
description: What is kept for a future fine-tuned model, which answers become examples, the JSONL formats and the export command.
---

# Fine-tuning dataset

Every answer is kept with the material needed to train a future model on reviewed
examples. Nothing is trained yet: this page describes the data and its export.

## What is kept for each question

| Data | Model and field | Since |
| --- | --- | --- |
| The question and its language | `Question.text`, `Question.lang` | the start |
| The exact evidence the writer received (Bayyinat passages with `[Q<n>]` markers) | `Interaction.evidence` | 2026-10-06 (empty before: no backfill) |
| The AI answer, kept sentences with their quotes, removed sentences with the reason | `Interaction.answer_text`, `sentences`, `dropped` | the start |
| The model and the prompt version | `Interaction.model_name`, `prompt_version` | the start |
| A reviewer's verdict: correct, to correct (with the corrected answer), wrong (with a reason) | `HumanLabel` ("AI verdicts" in the admin) | 2026-10-06 |
| A specialist's answer or correction shown to the asker | `AnswerRevision` | 2026-10-05 |

## Which answers become examples (`qa/dataset.py`)

Used: answers with kept evidence, without error, where the AI wrote an answer (`answer`
or `partial`; fixed replies teach nothing about answering).

| Case | SFT example (assistant turn) | DPO pair |
| --- | --- | --- |
| A reviewer's correction ("To correct") | the corrected answer | corrected answer preferred over the AI answer |
| Else a specialist's correction, clarification or answer | the newest revision | revision preferred over the AI answer |
| Else marked "Correct", and nobody marked it "Wrong" | the AI answer | none |
| Marked "Wrong", not reviewed, no evidence, or an error | excluded | excluded |

Never exported: the asker (account, email, session), reviewers' names, internal notes and
reasons.

## Formats

`sft.jsonl`, one example per line (chat format of supervised fine-tuning):

```json
{"messages": [
  {"role": "system", "content": "You answer questions about Islam for Musnid using only the evidence provided…"},
  {"role": "user", "content": "Question (en):\nDid Islam spread by the sword?\n\nEvidence:\n[Q229] …"},
  {"role": "assistant", "content": "No, it spread through invitation [Q229]."}
]}
```

`dpo.jsonl`, one preference pair per line (preference fine-tuning):

```json
{"input": {"messages": [{"role": "system", "content": "…"}, {"role": "user", "content": "…"}]},
 "preferred_output": [{"role": "assistant", "content": "the corrected answer"}],
 "non_preferred_output": [{"role": "assistant", "content": "the AI answer"}]}
```

With `--with-metadata`, each line also carries `metadata`: question `uuid`, language,
prompt version, model and source (`correction` or `approved_ai_answer`), for auditing;
leave it off for services that refuse extra keys.

## Export

```bash
.venv/bin/python manage.py export_finetuning [--since 2026-10-06] [--language ar] [--with-metadata]
```

Writes `data/finetuning/sft.jsonl` and `dpo.jsonl` (git-ignored: the examples contain
askers' questions) and prints how many usable answers, examples and pairs it found.
Read-only on the database. In production:
`docker compose exec web python manage.py export_finetuning --output /tmp/finetuning`.

## Limitations

- Answers saved before 2026-10-06 have no kept evidence and are never exported.
- The system prompt of the examples summarizes the writer's role (`agents/crews`); it is not
  the full multi-step flow (classification, verification), which stays in code.
- No example counts are given here: they depend on how many answers reviewers label.
