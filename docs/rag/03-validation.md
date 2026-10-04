---
id: validation
title: Validation results
sidebar_position: 3
description: Measured results of extraction, ingestion and search.
---

# Validation results

## Extraction (2026-10-04)

| Measure | Value |
| --- | --- |
| Questions | 263 (expected 263) |
| Alternative phrasings | 371 |
| `[آية]` placeholders | 1,869 |
| ﷺ in the output | 1,887 |
| Median summary length | 879 characters |
| Median detailed answer | 626 words |
| Warnings | 22 |

| Warning | Count | Verdict |
| --- | --- | --- |
| no alternative phrasings | 12 | book: 10 questions have no "عبارات مشابهة" label; 2 have the label without items |
| possible unrepaired ligature | 5 | genuine words: "أأنتَ", "اللاأدرية", "اللاأخلاقية", hyphenated letters |
| empty question | 2 | book: the 2-line title is the question (118, 235) |
| empty answer_summary | 2 | book: 261 summary labels for 263 questions |
| no detailed answer | 1 | book: 262 detailed labels |

## Ingestion (2026-10-04)

263 questions → 1,432 chunks (263 question, 261 summary, 908 answer; 259,085 words),
embedded in 15 batches, stored in 1 min 23 s.

## Search: first three queries (k = 5)

| Query | Top results (score, question) | Verdict |
| --- | --- | --- |
| هل انتشر الإسلام بالسيف؟ | 0.787 #229 (the same question), 0.483 #246, 0.474 #230 | exact match, margin 0.304 |
| لماذا خلقنا الله؟ | 0.648 #174 (why evil), 0.590 #4, 0.538 #178, 0.524 #12 (why worship) | no exact question in the book; relevant ones at ranks 3–4, covered by the top-3 evidence rule |
| ما هي عاصمة فرنسا؟ | 0.158 #195, 0.136 #99, 0.130 #37 | out of scope, far below in-scope scores |

Decisions from these results: `LOW_THRESHOLD = 0.30` as a starting value;
`EVIDENCE_QUESTIONS = 3`. Calibration with the 60-question evaluation is planned for
2026-10-06.
