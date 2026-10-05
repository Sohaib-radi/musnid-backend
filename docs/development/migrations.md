---
id: migrations
title: Migrations
sidebar_position: 3
description: Migration history of the project and the conventions for writing migrations.
---

# Migrations

## History

| App | Migration | Date | Content |
| --- | --- | --- | --- |
| `core` | `0001_initial` | 2026-10-04 | Enables the `vector` extension (first operation), then creates `User`, `Center`, `Membership` and their constraints: `unique_user_email_ci`, `only_one_default_center`, `unique_active_membership`, `membership_active_matches_left_at`. |
| `core` | `0002_center_review` | 2026-10-04 | Adds `status` (default `approved`, so existing centers become approved), `reviewed_at`, `reviewed_by`, `rejection_reason`, the help text of `is_active`, and the constraint `default_center_must_be_approved`. |
| `core` | `0003_api_credentials` | 2026-10-04 | Creates `ApiCredential` with `one_active_credential_per_provider` and `credential_active_matches_revoked_at`. |
| `knowledge` | `0001_initial` | 2026-10-04 | `SourceDocument`, `SourceChunk` (1536-dimension embedding, HNSW cosine index). Depends on `core.0001` for the `vector` extension. |
| `core` | `0004_ai_settings`, `0005_ai_settings_verifier_model` | 2026-10-04 | `AISettings` singleton (chat model, temperature), then `verifier_model`. |
| `qa` | `0001_initial` | 2026-10-04 | `Question` (center-owned, anonymous), `Interaction` (one per question), `HumanLabel`. |
| `knowledge` | `0002_source_document_pdf_url` | 2026-10-04 | Adds `SourceDocument.pdf_url` and help texts; sets the dawa.center page and PDF of an existing `bayyinat-ar` (no re-ingestion). |
| `qa` | `0004_answer_revision` | 2026-10-05 | Creates `AnswerRevision` ([ADR 0020](../architecture/decisions/0020-answer-revisions.md)); no data change. |
| `telegram_bot` | `0001_initial` | 2026-10-05 | Creates `TelegramMessage` ([ADR 0022](../architecture/decisions/0022-telegram-channel.md)); no data change. |
| `qa` | `0005_referral` | 2026-10-05 | Creates `Referral` ([ADR 0021](../architecture/decisions/0021-referral-tickets.md)); opens a ticket for every question already referred (answered when it has a revision, otherwise open). |
| `qa` | `0003_question_asker` | 2026-10-05 | Adds the nullable `Question.asker` (`SET_NULL`) and the index `question_asker_recent` (`asker`, `-created_at`); no data change ([ADR 0019](../architecture/decisions/0019-link-questions-to-logged-in-askers.md)). |
| `qa` | `0002_question_uuid_sentences` | 2026-10-04 | Adds `Question.uuid` in three steps (nullable, one value per existing row, then unique with a default), the index `question_session_recent` (`session_id`, `-created_at`), and `Interaction.sentences` and `Interaction.dropped`. |

Third-party apps bring their own migrations (`auth`, `admin`, `contenttypes`,
`sessions`, `token_blacklist`). `django_countries`, `pgvector.django`, `rest_framework`,
`drf_spectacular` and `corsheaders` have none.

## Conventions

- Generate with `.venv/bin/python manage.py makemigrations`, then read the file before
  committing. `core/tests/test_migrations.py` fails when a model change has no migration.
- A hand edit to a generated migration is explained in its docstring, as in
  `0001_initial` (the `VectorExtension` operation).
- Migrations that need extensions, data changes or locks are reviewed for production
  impact (table rewrites, long locks) before merging.

## Resetting the local database

Changing `AUTH_USER_MODEL` after `auth` and `admin` migrations were applied makes
`migrate` fail with `InconsistentMigrationHistory`. This happened once, when `core.User`
was introduced; the local `musnid` database held no data and was recreated:

```bash
docker exec musnid_backend_postgres sh -c \
  'psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE $POSTGRES_DB" -c "CREATE DATABASE $POSTGRES_DB"'
.venv/bin/python manage.py migrate
```

This deletes every row in the local database. Never run it against shared or production
data.
