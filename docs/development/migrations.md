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
