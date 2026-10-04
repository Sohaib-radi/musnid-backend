# CLAUDE.md

This file guides Claude Code when working in this repository.

## Mandatory rules (non-negotiable)

These rules apply to every change, without asking.

1. **Every change ships with tests.** New code gets new tests; changed behaviour gets
   updated tests. The full test suite must pass before work is reported as done.
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
  urls.py, wsgi.py, asgi.py
core/              shared app (no models yet)
  tests/           test package; one module per concern
docs/              Docusaurus content (Markdown only)
  getting-started/ local development, Docker, configuration
  architecture/decisions/  ADRs (NNNN-kebab-title.md)
  development/     testing and other practices
  technology-stack.md      every dependency: version, role, license
data/raw/, data/processed/ source books and extracted text (git-ignored)
Dockerfile, docker-compose.yml, .dockerignore
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
  `POSTGRES_PORT` (`5435`). Full reference: `docs/getting-started/configuration.md`.
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
.venv/bin/python manage.py runserver
docker compose --profile web up -d --build     # app in Docker (gunicorn)
docker compose --profile web down
```

## Ports

| Port (127.0.0.1) | Service |
| --- | --- |
| 5435 | PostgreSQL (`db`, container `musnid_backend_postgres`, volume `musnid_backend_pgdata`) |
| 8011 | Django via gunicorn (`web`, container `musnid_backend_web`, profile `web`) |
| 8000 | `manage.py runserver` (local) |

Other projects on the development machine use 5432, 5433, 6379, 8000, 8001 and 5555, and
the names `musnid_db` and `musnid_backend_db`. Do not reuse them.

<!-- Sections to be added as the project grows: Conventions. -->
