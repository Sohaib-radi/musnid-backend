---
id: 0015-knowledge-base-and-retrieval
title: "ADR 0015: Knowledge base and retrieval"
sidebar_position: 15
description: How vetted books become searchable chunks, and what the writer may read.
---

# ADR 0015: Knowledge base and retrieval

## Status

Accepted, 2026-10-04.

## Context

Answers must come from vetted sources only. The first source, "Bayyinat", is a 1,259-page
Arabic PDF of 263 questions whose text layer is in visual order with broken ligatures
(measured in [Extraction findings](../../rag/01-extraction-findings.md)).

## Decision

- **Extraction** with PyMuPDF 1.28.2, a tool-only dependency (`requirements-tools.txt`,
  AGPL-3.0, never shipped), into JSON outside git; lines rebuilt from character boxes.
- **Storage**: app `knowledge`, `SourceDocument` and `SourceChunk` (pgvector 1536
  dimensions, HNSW cosine index), read-only in the admin.
- **Chunks**: a `question` chunk (title, question, phrasings) only to find; `summary` and
  ~400-word `answer` chunks as evidence, each prefixed with the title.
- **Embeddings**: OpenAI `text-embedding-3-small` on Arabic-normalized text (Lucene
  direction), key from the encrypted credentials (ADR 0014), no SDK.
- **Search**: best chunk per question, score = 1 − cosine distance, `hnsw.ef_search`
  raised to the candidate count. The writer receives `get_evidence` for the top
  `EVIDENCE_QUESTIONS` (3) distinct questions, never question chunks. A best score below
  `LOW_THRESHOLD` (0.30, provisional) means the sources do not cover the question.

## Consequences

- Re-ingestion is idempotent and safe: embeddings are computed before old chunks are
  replaced.
- Quran verses appear as `[آية]` in evidence; the writer must not quote verses from them.
- The threshold must be recalibrated on the 60-question evaluation (2026-10-06).
