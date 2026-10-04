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

## Flow traces (2026-10-04, `ask_test`)

| Question | Level | Decision | Citations | Tokens in / out | Latency |
| --- | --- | --- | --- | --- | --- |
| هل انتشر الإسلام بالسيف؟ | B | answer | 229 | 29,552 / 800 | 18.3 s |
| لماذا خلقنا الله؟ | A | answer | 174, 178 | 21,042 / 500 | 13.0 s |
| ما هي عاصمة فرنسا؟ | out_of_scope | fixed refusal | none | 1,239 / 42 | 1.7 s |
| أنا متزوجة في فرنسا، هل يجوز لي العمل بدون إذن زوجي؟ | D | fixed referral | none | 1,253 / 48 | 1.8 s |
| Did Islam spread by the sword? | B | answer (English) | 229 | 29,570 / 817 | 17.6 s |

## Support check of the #229 answers (2026-10-04)

Each sentence was matched by hand to the evidence (#229's 7 chunks, 1,789 words).

| Verifier | Sentences kept | Unsupported claims |
| --- | --- | --- |
| gpt-4o-mini, rewrite | Arabic 6, English 7 | "الإسلام لم يُفرض… مما يدل على عدم الإكراه"; "migration to Medina was a strategic move… mutual support" |
| gpt-4o-mini, quotes + code check | Arabic 1 of 2, English 5 of 5 | English: "promise of safety and respect for their rights"; "predominantly peaceful" with a quote about the Ottoman conquest |
| gpt-4o, quotes + code check | Arabic 4 of 4, English 7 of 8 | Arabic: "لم يفرض الجزية إلا بعد أن استقر الدين في معظم القبائل" (the evidence only dates the jizya to year 8 or 9 AH) |

Re-run after requiring quotes in the evidence's original language (Arabic), 2026-10-04,
verifier gpt-4o: 0 sentences dropped in either answer (every quote was a real Arabic
passage), yet unsupported claims were kept: Arabic "…لم يفرض الجزية إلا بعد أن استقر
الإسلام في معظم المناطق… مما يدل على عدم الإكراه في الدين"; English "the migration to Medina…
allowed for the peaceful propagation of Islam". The quote check enforces provenance, not
entailment.

Re-run with the batched entailment check and the tightened writer prompt (2026-10-04,
verifier gpt-4o):

| Question | Decision | Kept | Dropped (reason) | Tokens in / out | Latency |
| --- | --- | --- | --- | --- | --- |
| هل انتشر الإسلام بالسيف؟ | answer | 4 sentences, close to the book's wording | 2 (quote reworded, e.g. "فذلك من جهة" for "فمِن جهة") | 31,597 / 1,775 | 45.6 s |
| Did Islam spread by the sword? | partial | 3 sentences | 2 (quote reworded) | 31,143 / 1,266 | 19.8 s |

No sentence was judged not_supported: the earlier unsupported inferences no longer
appeared once the writer was told to stay close to the evidence. The strict quote check
drops correct sentences whose quote is slightly reworded. The English question was labelled
"ar" by the classifier and got the Arabic partial note; the language is now decided by
script for Arabic.

### Quote match at 90% of words

Because the exact match dropped correct, slightly reworded sentences, a quote now matches
when 90% of its words appear in order in one passage of the evidence (ADR 0016). Measured
on 2026-10-04 against the evidence of #229, #246 and #230 (4,105 words after
normalization), with quotes built from the passage "الإسلامُ لم ينتشِرْ بالسيف، وإنما
انتشَرَ بالدعوةِ والحُجَّة، …":

| Quote | Result | Time |
| --- | --- | --- |
| Exact copy | match | 0.3 ms |
| 14 words, 1 changed ("دور" for "أثر") | match | 0.7 ms |
| 12 words, 1 dropped | match | 0.5 ms |
| 14 words, 2 changed | no match | 3.6 ms |
| 4 words reordered ("لم ينتشر الإسلام بالسيف") | no match (under 10 words: exact only) | 0.5 ms |
| Invented sentence | no match | 3.2 ms |

Re-run of the demo question with the new match (2026-10-04, local, verifier gpt-4o):

| Question | Decision | Kept | Key sentence "الإسلام لم ينتشر بالسيف" | Tokens in / out | Latency |
| --- | --- | --- | --- | --- | --- |
| هل انتشر الإسلام بالسيف؟ | answer (level B, coverage full) | 4 sentences, all citing #229 | absent | 33,068 / 2,946 | 35.8 s |

Dropped sentences were not saved at the time, so whether the writer omitted the key
sentence or a check removed it is unknown; `Interaction.dropped` now records every drop.

Decisions from these results: `LOW_THRESHOLD = 0.30` as a starting value;
`EVIDENCE_QUESTIONS = 3`. Calibration with the 60-question evaluation is planned for
2026-10-06.
