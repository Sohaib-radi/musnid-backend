---
id: development-log
title: Development log
sidebar_position: 4
description: Problems met while building the RAG pipeline and how they were fixed.
---

# Development log

| Date | Problem | Fix |
| --- | --- | --- |
| 2026-10-04 | Lam-alef ligatures extracted reversed, indistinguishable from a genuine "ال" in text | Detected from character boxes: the ligature's alef has zero width |
| 2026-10-04 | Spans and punctuation in visual order | Lines rebuilt from character x positions; LTR runs reversed back; brackets mirrored |
| 2026-10-04 | Tanween rule added a second alef to "جدًّا" (regex backtracked into the shadda) and an alef before ى in "هدًى" | Possessive quantifier; lookahead on alef and alef maksura |
| 2026-10-04 | Alternative phrasings merged | The bullet "3" sits 6 pt off the text baseline and formed its own line; a bullet-only line now marks the next line |
| 2026-10-04 | ﷺ dropped from a title (set in a body font on the title line) | Title keeps every character except the "المسألة" label |
| 2026-10-04 | Validator flagged 255 questions for "unrepaired ligatures" | It matched the correct "الأ…"; it now flags two adjacent alefs |
| 2026-10-04 | "الدَّلاالت" in 3 questions | In-word "لاال" repaired to "لالا" |
| 2026-10-04 | CrewAI's first-run "view traces? [y/N]" prompt blocked `ask_test` despite the telemetry switches | Decline recorded with `mark_first_execution_done(user_consented=False)` at import |
| 2026-10-04 | The Docker answer to the demo question lost its key sentence "الإسلام لم ينتشر بالسيف": its quote was slightly reworded | Quote match loosened to 90% of words, in order, in one passage (`quote_matches`); entailment still judges support |
| 2026-10-04 | After the 90% match the demo answer still lacked the key sentence, and the drop could not be inspected | Kept and dropped sentences saved on `Interaction` (`sentences`, `dropped`); `ask_test` prints them |
| 2026-10-04 | The UI needs each sentence linked to its source; the writer's `[Q<n>]` is not proof | The source is the evidence question whose text contains the quote, found in code; a quote must lie within one question's evidence |
| 2026-10-04 | The prompt came back in a fresh Docker container (twice in one `ask_test`, up to 20 s each) | CrewAI decides when it is imported, before the decline in `agents/flow.py` ran; `AgentsConfig.ready()` now writes the decline before any CrewAI import (`agents/tracing.py`) |
| 2026-10-04 | Flow never ended | Listener methods named like router labels (`answer`, `refer`, `abstain`) re-triggered themselves; renamed |
| 2026-10-04 | gpt-4o-mini returned the JSON schema instead of a classification | Structured outputs (`response_format`) |
| 2026-10-04 | Verifier dropped every `[Q<n>]` citation, so every answer became a referral | Field description requiring the markers; later replaced by sentences with quotes |
| 2026-10-04 | Unsupported claims kept by the verifier | Sentences with quotes checked in code; verifier on gpt-4o |
| 2026-10-04 | Flow tests found no data; test database not droppable | CrewAI runs steps in worker threads: `TransactionTestCase`, and worker connections closed after retrieval |
