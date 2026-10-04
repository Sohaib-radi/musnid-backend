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

API tests subclass `api.tests.base.APITestCase`, which clears the cache before each test
(throttling counts requests in it) and offers `url()`, `authenticate()` and `assertError()`.

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

All modes were last run in step 2 (serial, `--parallel 4`, `--keepdb` twice); since then each step runs the suite once, serially.

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
| `core/tests/test_admin.py` | 37 | Every admin and inline uses Unfold; pages respond; user creation and case-insensitive email error; center languages checkboxes, second-default form error, make-default action; membership add/change through the services, rule violations as form errors, offboard action messages (singular, plural, refusals), no deletion.; center review: badge, Review column and dialogs on pending rows only, change-page buttons, POST-only review URLs, permission 403, bulk approve and reject (reason page), sidebar badge. |
| `core/tests/test_base.py` | 14 | `BaseModel` timestamps and ordering, `for_center` scoping, `CASCADE` from center, `created_by` `SET_NULL`, reverse accessors. |
| `core/tests/test_center.py` | 19 | Center fields and uniqueness, `only_one_default_center` (translated message in ar and fr, database backstop), `make_default`.; review status, `operational()`, `pending()`, `default_center_must_be_approved`. |
| `core/tests/test_choices.py` | 2 | `Language` matches `settings.LANGUAGES`. |
| `core/tests/test_database.py` | 3 | Connection to PostgreSQL, a query round trip, pgvector available on the server. |
| `core/tests/test_env.py` | 12 | `config.env` readers: required, optional, strict boolean, comma-separated lists, empty treated as unset. |
| `core/tests/test_i18n.py` | 6 | Languages, `LocaleMiddleware` position, both `LOCALE_PATHS` in order, right-to-left Arabic, the `set_language` URL and cookie. |
| `core/tests/test_membership.py` | 15 | Membership defaults, both constraints, `full_clean` messages, querysets. |
| `core/tests/test_migrations.py` | 4 | `vector` installed and usable, `VectorExtension` is the first operation, no missing migrations. |
| `core/tests/test_runner.py` | 3 | Test-only tables exist, fast hasher active, `core.tests.parallel` imports before `django.setup()`. |
| `core/tests/test_services_centers.py` | 8 | `register_center` (pending, applicant as admin, unique slug), `approve`, `reject` (reason required), only pending centers reviewed, reviewer deletion. |
| `core/tests/test_services_memberships.py` | 30 | `add_member`, `change_role`, `offboard` and the check-only `validate_add_member`, `validate_change_role`: every error code and the last-admin rule. |
| `core/tests/test_translations.py` | 13 | Both catalogs (project, Unfold vendor) in ar and fr: complete, not fuzzy, French allowlist, `.mo` current, extraction current (temporary copy, skipped without gettext); labels, choices, actions, sidebar translated; login and center pages rendered in ar (`dir="rtl"`) and fr. |
| `core/tests/test_unfold.py` | 13 | Brand colour anchors, scales ordered, WCAG AA contrast of the text pairs, no colour in `admin.css` but the accent, fonts and licence, login image, app order, site title, sidebar icons, links and permissions. |
| `core/tests/test_settings.py` | 6 | `config.settings` imported in a fresh process: a clear error for each missing required variable, `DJANGO_DEBUG` parsing, database and CORS origin defaults and overrides. |
| `core/tests/test_user.py` | 18 | User defaults, case-insensitive email uniqueness and login, `create_user`, `create_superuser`. |
| `api/tests/test_admin.py` | 2 | Token blacklist admins use Unfold; "Security" sidebar group. |
| `api/tests/test_auth.py` | 14 | Both registrations, login (any email case, uuid claim), refresh rotation and blacklist, logout, throttling of the `auth` scope. |
| `api/tests/test_centers.py` | 11 | Center detail for members in any state, dashboard and settings (403 codes, `center_not_operational`, 404 for non-members, 401), settings validation codes, messages in ar and fr. |
| `api/tests/test_cors.py` | 4 | Allowed origin on `/api/`, other origins refused, no CORS on the admin, CORS headers on errors, no credentials. |
| `api/tests/test_errors.py` | 7 | Exception handler: domain errors to 400 with code, field `codes`, DRF and Django errors with codes; permission codes. |
| `api/tests/test_me.py` | 8 | Profile GET and PATCH, no PUT, memberships with center states, countries translated. |
| `api/tests/test_memberships.py` | 11 | List, add by email, change role, offboard, service codes, no DELETE, other centers 404, permissions, pending center blocked. |
| `api/tests/test_schema.py` | 3 | Schema without warnings, public identifiers only, docs page on sidecar assets. |
| **Total** | **263** | |

Last full run: 263 tests, all passing, none skipped, 43.0 s serial, on 2026-10-04. The extraction tests and the settings tests start
subprocesses and account for most of the serial time.

## Language state between tests

`LocaleMiddleware` activates the request's language on the test thread and does not
reset it. Tests that send `Accept-Language` restore the default language in a cleanup
(`translation.activate(settings.LANGUAGE_CODE)`); without it, later tests saw Arabic
strings and failed, as observed while writing `test_translations.py`.

## How the settings tests work

Settings are evaluated once per process, so `test_settings.py` imports
`config.settings` in a subprocess with a controlled environment and reads the result as
JSON. Required variables are passed explicitly so the tests do not depend on the
developer's `.env`. To simulate a missing variable, the test passes it as an empty
string. python-dotenv does not override variables that are already set, and
`config.env` treats empty as unset.
