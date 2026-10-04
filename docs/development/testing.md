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
interfere with each other. `--parallel N` within one run is fine, and so is `--keepdb`.

## Database

Tests run against **PostgreSQL, not SQLite**: pgvector has no SQLite equivalent, and
tests must exercise the same database as production. Django creates a separate database
named `test_` followed by `POSTGRES_DB` (for example `test_musnid`) and drops it at the
end. The configured role therefore needs the `CREATEDB` privilege; the role created by
the `db` container is a superuser, so this holds locally.

## Test runner

`TEST_RUNNER = 'core.tests.runner.TestRunner'`, a `DiscoverRunner` subclass that:

- **creates the tables of test-only models** (`TEST_ONLY_MODELS` in
  `core/tests/support.py`, currently `Note`). They have no migration; a `post_migrate`
  handler, connected only while the test databases are built, creates them after
  migrations and before `--parallel` clones the database. With `--keepdb`, existing
  tables are skipped.
- **uses a fast password hasher** (MD5) instead of PBKDF2. Measured before the change,
  the full suite took 51.5 s, with single login tests at up to 8.8 s; after it, 7.3 s.
  The hasher is applied in the main process and, through
  `core.tests.parallel.FastHasherParallelTestSuite`, in every spawned `--parallel`
  worker.

`core/tests/parallel.py` must never import models. Spawned workers import it before
`django.setup()`; a model import there crashes every worker at start-up and the pool
respawns them endlessly, so the run hangs instead of failing. This happened during
development and is covered by `test_runner.py`.

All modes were run on 2026-10-04: serial, `--parallel 4`, and `--keepdb` twice in a row.

## Test support

`core/tests/support.py` provides:

| Helper | Creates |
| --- | --- |
| `make_user(**fields)` | A user with a unique email and name; unusable password unless `password` is given. |
| `make_center(**fields)` | An active, non-default center with a unique name and slug. |
| `make_membership(**fields)` | An active specialist membership; new user and center unless given. |
| `make_note(**fields)` | A test-only `Note` in a new center unless given. |

Tests create objects through these factories, not `objects.create()`, so a new required
field is handled in one place.

## Test modules

| File | Tests | Covers |
| --- | --- | --- |
| `core/tests/test_base.py` | 14 | `BaseModel` timestamps and ordering, `for_center` scoping, `CASCADE` from center, `created_by` `SET_NULL`, reverse accessors. |
| `core/tests/test_center.py` | 14 | Center fields and uniqueness, `only_one_default_center` (translated message in ar and fr, database backstop), `make_default`. |
| `core/tests/test_choices.py` | 2 | `Language` matches `settings.LANGUAGES`. |
| `core/tests/test_database.py` | 3 | Connection to PostgreSQL, a query round trip, pgvector available on the server. |
| `core/tests/test_env.py` | 12 | `config.env` readers: required, optional, strict boolean, comma-separated lists, empty treated as unset. |
| `core/tests/test_i18n.py` | 7 | Languages, `LocaleMiddleware` position, `LOCALE_PATHS`, right-to-left Arabic, every catalog entry translated and not fuzzy, compiled `.mo` files match the `.po` files. |
| `core/tests/test_membership.py` | 15 | Membership defaults, both constraints, `full_clean` messages, querysets. |
| `core/tests/test_migrations.py` | 4 | `vector` installed and usable, `VectorExtension` is the first operation, no missing migrations. |
| `core/tests/test_runner.py` | 3 | Test-only tables exist, fast hasher active, `core.tests.parallel` imports before `django.setup()`. |
| `core/tests/test_services_memberships.py` | 21 | `add_member`, `change_role`, `offboard`: every error code and the last-admin rule. |
| `core/tests/test_settings.py` | 6 | `config.settings` imported in a fresh process: a clear error for each missing required variable, `DJANGO_DEBUG` parsing, database defaults and overrides. |
| `core/tests/test_user.py` | 18 | User defaults, case-insensitive email uniqueness and login, `create_user`, `create_superuser`. |
| **Total** | **119** | |

Last full run: 119 tests, all passing, 7.3 s serial and 18.1 s with `--parallel 4`
(worker start-up dominates at this size), on 2026-10-04.

## How the settings tests work

Settings are evaluated once per process, so `test_settings.py` imports
`config.settings` in a subprocess with a controlled environment and reads the result as
JSON. Required variables are passed explicitly so the tests do not depend on the
developer's `.env`. To simulate a missing variable, the test passes it as an empty
string. python-dotenv does not override variables that are already set, and
`config.env` treats empty as unset.
