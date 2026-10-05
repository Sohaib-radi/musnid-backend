# CLAUDE.md

This file guides Claude Code when working in this repository.

## Mandatory rules (non-negotiable)

These rules apply to every change, without asking.

1. **Every change ships with tests.** New code gets new tests; changed behaviour gets
   updated tests. Tests are written with the code but **run only with the user's
   permission**, and only the tests the user asks for (see Working agreement). Report
   which tests were run, or that none were.
2. **Every piece of code is documented.** Modules, classes and public methods have
   docstrings covering purpose, arguments and non-obvious behaviour. Comments explain
   *why*, not *what*.
3. **Respect design principles.** SOLID, DRY, separation of concerns, and idiomatic
   Django: fat models / thin views, custom QuerySets and managers, mixins, and service
   modules for business rules that span several objects.
4. **Every user-facing string is translated into Arabic and French in the same commit.**
   Workflow: `makemessages` → translate both `.po` files → `msgfmt --check` →
   `compilemessages` → commit the `.po` and `.mo` files together. Brand names are not
   translated.
5. **Every RAG step is documented in `docs/rag/`.** This covers findings with measured
   evidence, decisions with rationale, processing stages, validation results, a
   development log of problems and fixes, and known limitations. Never document numbers
   that were not measured.
6. **Every change updates the documentation in `docs/` in the same commit.** Docs are
   professional reference material for experienced engineers.
   - Significant design choices get an ADR in `docs/architecture/decisions/`, named
     `NNNN-kebab-title.md`, with the sections Status, Context, Decision, Consequences.
   - Every new dependency is listed in `docs/technology-stack.md` with its version, role
     and license.

## Working agreement

- Never delete, move or overwrite files, and never run destructive commands (`rm`,
  `git reset --hard`, `git clean`, `git push --force`), without asking the user first.
- Run tests only when the user asks, like commit and push: ask for permission first,
  run only what the user names, never the whole suite unless the user says so.
- Commit and push only when asked. Commit messages are descriptive: a title, then what
  changed and why.
- Before choosing an architecture the spec does not dictate, check the framework's
  documented conventions and propose it to the user first.
- Never run two test runs at the same time.
- Never commit `.env`, secrets, source books (`data/raw/`) or extracted text
  (`data/processed/`).
- Never print the contents of `.env` or any secret.

## Commit messages

Every commit message follows this pattern:

    <Title: the outcome of the commit, imperative mood, one line, no trailing period>

    <One short paragraph: what changed and why it matters.>

    <Group heading>:
    - detail, with the reason when it is not obvious

    Documentation: <pages added or updated>.

    Tests: <count> (was <previous count>).

Rules:
- The title states what the commit achieves, never "update files".
- The body explains why; details are grouped by area.
- Every number is measured, never estimated.
- Mention known limitations and decisions taken.
- Show the full message to the user before committing.

## Token economy

- Reports are short: a results table, the decisions the user must take, and the commit
  message. Do not repeat what is already in the commit message or the docs.
- Filter output before reading it (grep, tail, head); never print whole library source
  files, full test outputs or long tracebacks when one line is enough.
- Check a library's API (one grep in site-packages or its docs) before writing code
  against it.
- Never leave a command running that looks stuck: stop it after 2 minutes without output
  and investigate.
- Verification defaults, unless the user asks for more:
  - no test run without the user's permission; when permitted, only the tests the user
    names;
  - no screenshots;
  - wheel checks on the 3 platforms only for newly added dependencies;
  - measure only what the docs or the commit message will state.

## Project

Backend for the competition "AI Challenge – Serving Islamic Content". The service answers
questions about Islam from vetted sources using retrieval-augmented generation (RAG) and
AI agents. Questions the AI must not answer are routed to centers of specialists, who
receive and answer them.

## Layout

```
config/            Django project package
  settings.py      all settings, read from the environment
  env.py           typed env readers (required, optional, flag, csv_list)
  unfold.py        UNFOLD settings: brand colours, sidebar, login image (the only place for colours)
  api.py           REST_FRAMEWORK, SIMPLE_JWT, SPECTACULAR_SETTINGS
  urls.py, wsgi.py, asgi.py
core/              domain app
  models/          one module per concern, all re-exported from core/models/__init__.py
    base.py        BaseModel, CenterLinkedModel, CenterQuerySet, CreatedByMixin
    choices.py     Language (must match settings.LANGUAGES)
    user.py        User, UserManager (email login)
    center.py      Center (single default)
    membership.py  Membership, MembershipQuerySet
  services/        rules spanning several objects (memberships.py, centers.py: registration and review)
  admin.py         Unfold admins: User, Center, Membership, Group
  forms.py         admin forms (Unfold user forms rebound to core.User, center, membership)
  static/core/     admin.css (font, accent, RTL fixes), fonts/readex-pro/, img/login.svg
  migrations/      0001_initial enables pgvector first
  tests/           one test_*.py per module
    support.py     factories (make_user, make_center, make_membership) and test-only models
    runner.py      TEST_RUNNER: test-only tables, fast password hasher
    parallel.py    --parallel worker setup; must never import models
knowledge/         RAG: SourceDocument, SourceChunk, normalize, chunking, embeddings, services/search
  extraction/      PDF text repair and Bayyinat parsing (never imports PyMuPDF)
  management/commands/  extract_bayyinat (PyMuPDF), ingest_bayyinat, search_test
qa/                Question, Interaction, AnswerRevision, Referral, HumanLabel; services.py (revise, referrals); admin
agents/            CrewAI: flow.py (steps, routing, fixed replies), services.py (ask), crews/ (YAML)
telegram_bot/      Telegram channel (ADR 0022): client.py (Bot API over httpx), services.py (notify_referral,
                   resend), receivers.py (qa.signals.referral_opened), TelegramMessage log; telegram_chats command
api/               REST API, no models
  v1/urls.py       explicit paths; views/ and serializers/ per area (auth, centers, memberships)
  v1/views/mixins.py  CenterScopedMixin: non-members get 404
  permissions.py   IsCenterMember, IsCenterAdmin, IsOperationalCenter (each with a code)
  authentication.py OptionalJWTAuthentication: public views, a stale token never 401s
  schema.py        drf-spectacular extensions (OptionalJWTScheme reuses jwtAuth)
  exceptions.py    EXCEPTION_HANDLER: "code" next to "detail", "codes" for field errors
  admin.py         token blacklist admins with Unfold
  tests/base.py    APITestCase: url(), authenticate(), assertError(); clears the throttle cache
locale/            ar and fr catalogs (.po and .mo, both committed)
locale_vendor/unfold/  our ar and fr translations of Unfold's strings (Unfold ships none)
docs/              Docusaurus content (Markdown only)
  getting-started/ local development, Docker, configuration, deployment (VPS)
  architecture/decisions/  ADRs (NNNN-kebab-title.md)
  reference/       models and admin: every field, constraint, admin, action
  development/     testing, translations, migrations
  technology-stack.md      every dependency: version, role, license
data/raw/, data/processed/ source books and extracted text (git-ignored)
Dockerfile, docker-compose.yml, .dockerignore
deploy/nginx/       production nginx site for api.musnid.online (ADR 0018)
requirements.txt   exact pins (pip freeze)
.env.example       template for .env
```

## Configuration

- Python 3.12 only (ADR 0001: CrewAI 1.9.3 and onnxruntime 1.19.2 on macOS 12 Intel).
- Settings come from environment variables, loaded from `.env` at the repository root by
  python-dotenv; process variables win over `.env`. All parsing goes through
  `config/env.py`: empty means unset, required variables raise `ImproperlyConfigured`
  at import, `DJANGO_DEBUG` is on only for the exact string `True`.
- Required: `DJANGO_SECRET_KEY`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`.
  Optional: `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `POSTGRES_HOST` (`localhost`),
  `POSTGRES_PORT` (`5435`), `DJANGO_HTTPS` and `DJANGO_HSTS_SECONDS` (production only, ADR 0018),
  `TELEGRAM_BOT_TOKEN` (empty: bot off) and `DJANGO_SITE_URL` (ADR 0022). Full reference: `docs/getting-started/configuration.md`.
  A new variable must be added to `.env.example` and that page.
- Secret values must use a URL-safe alphabet: Compose interpolates `$` in env files.
- `requirements.txt` holds exact pins only. Install with
  `pip install --only-binary=:all: -r requirements.txt`. python-dotenv must stay 1.1.x.
- Database is PostgreSQL with pgvector in development and tests too (never SQLite).

## Common commands

```bash
docker compose up -d db                        # start PostgreSQL + pgvector
.venv/bin/python manage.py check
.venv/bin/python manage.py migrate
.venv/bin/python manage.py test                # needs the db service running
.venv/bin/python manage.py makemessages -l ar -l fr --ignore=.venv --ignore=docs --ignore=staticfiles --ignore=media --ignore=data
.venv/bin/python manage.py compilemessages --ignore=.venv
.venv/bin/python manage.py runserver
docker compose --profile web up -d --build     # app in Docker (gunicorn)
docker compose --profile web down
.venv/bin/python manage.py spectacular --validate --fail-on-warn --file /dev/null   # API schema check
```

## Ports

| Port (127.0.0.1) | Service |
| --- | --- |
| 5435 | PostgreSQL (`db`, container `musnid_backend_postgres`, volume `musnid_backend_pgdata`) |
| 8011 | Django via gunicorn (`web`, container `musnid_backend_web`, profile `web`) |
| 8000 | `manage.py runserver` (local) |
| 8010 | `manage.py runserver` used for admin screenshots |

Other projects on the development machine use 5432, 5433, 6379, 8000, 8001 and 5555, and
the names `musnid_db` and `musnid_backend_db`. Do not reuse them.

## Conventions

- **User model:** `AUTH_USER_MODEL = 'core.User'`. Refer to it as `settings.AUTH_USER_MODEL`
  in foreign keys and `get_user_model()` in code, never `django.contrib.auth.models.User`.
  Login is by email, case-insensitive; look users up with `email__iexact`.
- **Public identifiers:** never expose integer primary keys outside the backend (URLs,
  API payloads, Telegram callbacks). Use the model's `uuid` field.
- **Models:** concrete models subclass `BaseModel`. A model with its own `Meta` writes
  `class Meta(BaseModel.Meta):` to keep the `-created_at` ordering.
- **`updated_at`:** `save(update_fields=[...])` must include `'updated_at'`, and
  `QuerySet.update()` must set `updated_at=timezone.now()`; `auto_now` does not run otherwise.
- **Center scoping:** center-owned models subclass `CenterLinkedModel`. Its default manager is
  not scoped: every query on behalf of a center calls `for_center(center)` explicitly (ADR 0005).
- **Memberships:** users reach centers only through `Membership`. Change memberships through
  `core.services.memberships` (`add_member`, `change_role`, `offboard`), never by direct
  saves; deactivate (`offboard`), never delete.
- **Services:** rules spanning several objects go in `core/services/`, run in a transaction
  with row locks where needed, and raise `ValidationError` with a `code`.
- **Constraints:** name every database constraint and give it a translated
  `violation_error_message`.
- **Tests:** create objects with the factories in `core/tests/support.py`. A test-only model
  goes in `support.py` and in `TEST_ONLY_MODELS`.
- **Translations:** wrap user-facing strings with `gettext_lazy as _`, named placeholders
  only; plurals with `ngettext` (Arabic needs six forms). Workflow and glossary:
  `docs/development/translations.md`. Developer-facing exceptions stay in English.
  `core/tests/test_translations.py` enforces completeness (ADR 0009).
- **Vendor strings:** translations of a third-party package's strings go in
  `locale_vendor/<package>/` (listed in `LOCALE_PATHS`), never in `site-packages`. Refresh
  `locale_vendor/unfold` after upgrading Unfold. French words identical to English need
  an entry in `FRENCH_SAME_AS_ENGLISH`.
- **Admin:** every admin inherits `unfold.admin.ModelAdmin`, every inline Unfold's
  `TabularInline`/`StackedInline`; re-register third-party models with an Unfold admin.
  Forms live in `core/forms.py`. Admins never bypass services: memberships save through
  `core.services.memberships`, their inlines are read-only. Action messages use `ngettext`.
  Reference: `docs/reference/admin.md`.
- **Colours:** defined only in `config/unfold.py` (ADR 0008). The single exception is the
  turquoise accent in `core/static/core/css/admin.css`, used only on navy. Any palette
  change must keep WCAG AA; `core/tests/test_unfold.py` measures it.
- **API:** under `/api/v1/`, public identifiers only (user `uuid`, center `slug`,
  membership `uuid`). Views stay thin; serializers validate and call `core.services`.
  Center endpoints use `CenterScopedMixin` (404 for non-members) and permissions with
  codes (403). Every error carries a `code`; clients branch on codes. `PATCH` only, no
  `PUT`, no `DELETE`. New endpoints must keep `spectacular --validate --fail-on-warn`
  clean (annotate with `extend_schema`). Reference: `docs/reference/api.md`.
- **Secrets:** never log, print, display or return a secret (API keys, tokens), and never
  put one in an exception message. Provider keys only through `core.services.credentials`
  (`add_credential`, `revoke`, `get_openai_key`); mark functions holding one with
  `sensitive_variables`. Encryption keys come from `FIELD_ENCRYPTION_KEYS`, never `SECRET_KEY`.
- **RAG:** extraction findings, decisions, validation and limitations go in `docs/rag/`
  with measured numbers only. PyMuPDF stays in `requirements-tools.txt` (AGPL). The
  writer only ever receives `get_evidence()` chunks, never question chunks.
- **Agents:** answers come only from `get_evidence()`; the verifier must return quotes, checked
  in code; decisions and fixed replies are code, never generated. Flow handler names must
  differ from router labels. Change prompts in the crews' YAML (the prompt version follows).
  Model choice lives in AISettings (verifier on gpt-4o).
- **Answers:** change what the asker sees only through `qa.services.revise` (a new
  `AnswerRevision`); never edit an `Interaction`, it is the audit record (ADR 0020).
- **Referrals:** a `refer` decision opens a `Referral` in `ask()`; change it only through
  `qa.services` (`assign`, `close`, `revise`), never by direct saves (ADR 0021).
- **Telegram:** `telegram_bot` is a channel: it calls services and listens to `qa.signals`,
  `qa` never imports it. The bot token never appears in an error, log or output; tests use
  `telegram_bot.tests.support.FakeClient` (the runner empties the token) (ADR 0022).
- **Center review:** never edit `Center.status` directly; use
  `core.services.centers.approve`/`reject`. Center-admin endpoints require an operational
  center (approved and active).
- **Right-to-left:** check admin changes in Arabic. Fix Unfold's physical left/right
  spacing in `admin.css` under `html[dir="rtl"]`; wrap LTR values inside Arabic text in
  U+2066 … U+2069.
