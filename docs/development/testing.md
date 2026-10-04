---
id: testing
title: Testing
sidebar_position: 1
description: How to run the test suite, what it needs, and what each test module covers.
---

# Testing

The suite uses Django's test runner (`unittest`). No extra test dependencies are installed.

## Running the tests

```bash
docker compose up -d db              # the tests need the real database
.venv/bin/python manage.py test      # full suite
.venv/bin/python manage.py test core.tests.test_env   # one module
```

Run one test process at a time: concurrent runs share the same test database name and
interfere with each other.

## Database

Tests run against **PostgreSQL, not SQLite**: pgvector has no SQLite equivalent, and
tests must exercise the same database as production. Django creates a separate database
named `test_` followed by `POSTGRES_DB` (for example `test_musnid`) and drops it at the
end. The configured role therefore needs the `CREATEDB` privilege; the role created by
the `db` container is a superuser, so this holds locally.

## Test modules

| File | Tests | Covers |
| --- | --- | --- |
| `core/tests/test_env.py` | 12 | `config.env` readers: required, optional, strict boolean, comma-separated lists, empty treated as unset. |
| `core/tests/test_settings.py` | 6 | `config.settings` as imported from a fresh process: a clear error for each missing required variable, `DJANGO_DEBUG` parsing, database defaults and overrides. |
| `core/tests/test_database.py` | 4 | Connection to PostgreSQL, a query round trip, the `vector` extension is available and works. |
| **Total** | **22** | |

Last full run: 22 tests, all passing, 2.7 seconds, on 2026-10-04.

## How the settings tests work

Settings are evaluated once per process, so `test_settings.py` imports
`config.settings` in a subprocess with a controlled environment and reads the result as
JSON. Required variables are passed explicitly so the tests do not depend on the
developer's `.env`. To simulate a missing variable, the test passes it as an empty
string. python-dotenv does not override variables that are already set, and
`config.env` treats empty as unset.

## The pgvector test

`test_vector_extension_can_be_enabled_and_used` runs `CREATE EXTENSION IF NOT EXISTS
vector` inside the test transaction, which is rolled back afterwards. The extension is
not enabled permanently yet; the first migration that needs vectors will do that.
