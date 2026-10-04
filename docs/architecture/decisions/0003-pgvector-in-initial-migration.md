---
id: 0003-pgvector-in-initial-migration
title: "ADR 0003: Enable pgvector in the initial migration"
sidebar_position: 3
description: Why the vector extension is created by the first operation of core's first migration.
---

# ADR 0003: Enable pgvector in the initial migration

## Status

Accepted, 2026-10-04.

## Context

Retrieval-augmented generation will store embeddings in PostgreSQL with pgvector. The
`vector` type exists only after `CREATE EXTENSION vector` has run in the database. The
extension must therefore exist before any migration creates a `VectorField`, in every
database: development, test and production.

Options considered:

1. Enable it manually or in a container init script: easy to forget in a new
   environment, and the test database would not get it.
2. Enable it in the migration that adds the first vector column: correct, but couples
   the extension to whichever app happens to need it first.
3. Enable it in `core`'s first migration, before anything else.

## Decision

`core/migrations/0001_initial.py` starts with `pgvector.django.VectorExtension()`.
It is the first operation of the first migration of the app every other app depends on.

## Consequences

- Every database built by `migrate`, including each test database, has the extension.
  Tests check that it is installed and that it is the first operation.
- `VectorExtension` skips creation when the extension already exists, so re-running is
  safe.
- The migrating role must be allowed to create the extension. The role created by the
  `pgvector/pgvector` image is a superuser. A managed PostgreSQL service in production
  must provide pgvector and grant the right to create it, or have it pre-created.
- The pgvector version is the one shipped with the image (measured: 0.8.7 in
  `pgvector/pgvector:pg17` on 2026-10-04).
