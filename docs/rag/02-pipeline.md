---
id: pipeline
title: Pipeline and decisions
sidebar_position: 2
description: The processing stages from PDF to search results, and the decisions behind each.
---

# Pipeline and decisions

```
PDF ─extract_bayyinat→ data/processed/bayyinat_ar.json ─ingest_bayyinat→ SourceDocument + SourceChunk ─search()→ questions ─get_evidence()→ writer
```

## 1. Extraction (`manage.py extract_bayyinat`)

- PyMuPDF 1.28.2 (AGPL-3.0) is a **tool dependency** in `requirements-tools.txt`, imported
  only inside the command; it is never in `requirements.txt` or the Docker image. The
  parsing modules (`knowledge/extraction/`) work on plain dicts and do not import it.
- Lines rebuilt from character boxes; repairs as listed in
  [Extraction findings](01-extraction-findings.md).
- Output, one object per question: `number`, `part`, `chapter`, `title`, `question`,
  `alternative_phrasings[]`, `keywords[]` (empty: the book has none), `answer_sections`
  (`content`, `summary`, `detailed`, `conclusion`, paragraphs separated by newlines),
  `answer_summary`, `page_start`, `page_end` (printed page numbers).
- `data/processed/` is git-ignored: the text is not redistributed.

## 2. Chunking (`knowledge/chunking.py`)

| Kind | Content | Use |
| --- | --- | --- |
| `question` | title + question + alternative phrasings | finding only; never given to the writer |
| `summary` | title + summary | evidence |
| `answer` | title + a piece of ~400 words of `content`, `detailed`, `conclusion`, split on paragraphs | evidence |

Decision: phrasings people use are in the question chunk, so a query matches the
question even when the answer uses other words; the writer only sees answer text.

## 3. Normalization (`knowledge/normalize.py`)

Applied to `text_norm` and to queries, never to displayed text. Lucene
`ArabicNormalizer` direction: alef forms → ALEF, TEH MARBUTA → HEH, ALEF MAKSURA → YEH,
tatweel and harakat removed; ALEF WASLA and SUPERSCRIPT ALEF added.

## 4. Embeddings and ingestion (`manage.py ingest_bayyinat`)

- OpenAI `text-embedding-3-small`, 1536 dimensions, on the normalized text; batches of
  100; key from `core.services.credentials.get_openai_key()`; HTTP via the standard
  library (no SDK dependency).
- Idempotent by slug (`bayyinat-ar`): embeddings are computed first; then, in one
  transaction, the old chunks are deleted and the new ones inserted.
- Index: HNSW, cosine (`vector_cosine_ops`), m = 16, ef_construction = 64.

## 5. Search (`knowledge.services.search`)

- `search(query, k)`: normalize, embed, fetch `max(40, 8k)` nearest chunks with
  `SET LOCAL hnsw.ef_search` raised to that number (the default 40 would cap recall),
  keep the best chunk per question, score = 1 − cosine distance.
- `get_evidence(question_numbers)`: summary then answer chunks of those questions, in the
  given order. The writer receives only these.
