---
id: local-development
title: Local development
sidebar_position: 1
description: Set up a Python 3.12 virtualenv, start PostgreSQL in Docker and run Django locally.
---

# Local development

The application runs from a local virtualenv; PostgreSQL (with pgvector) runs in Docker.

## Prerequisites

- Python 3.12, available as `python3.12`. The version is fixed by
  [ADR 0001](../architecture/decisions/0001-python-3-12.md).
- Docker with Docker Compose v2.
- GNU gettext, to update translations (`brew install gettext` on macOS).

## First-time setup

```bash
# 1. Virtualenv and dependencies (wheels only, no compilation)
python3.12 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install --only-binary=:all: -r requirements.txt

# 2. Configuration
cp .env.example .env
# then set DJANGO_SECRET_KEY and POSTGRES_PASSWORD in .env

# 3. Database
docker compose up -d db

# 4. Schema, and the cache table used by the API throttles (ADR 0017)
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createcachetable
```

`--only-binary=:all:` makes pip fail instead of compiling from source. Every pinned
package ships a prebuilt wheel for the supported platforms; see
[Technology stack](../technology-stack.md#platform-wheel-coverage).

## Daily commands

| Task | Command |
| --- | --- |
| Start the database | `docker compose up -d db` |
| System check | `.venv/bin/python manage.py check` |
| Apply migrations | `.venv/bin/python manage.py migrate` |
| Create the cache table (once; idempotent) | `.venv/bin/python manage.py createcachetable` |
| Run the tests | `.venv/bin/python manage.py test` |
| Development server | `.venv/bin/python manage.py runserver` |
| Create an admin user | `.venv/bin/python manage.py createsuperuser` (asks for email and full name) |
| Update translations | see [Translations](../development/translations.md) |

The development server listens on `http://127.0.0.1:8000/`. Set `DJANGO_DEBUG=True` in
`.env` for local work so that `runserver` serves static files and shows error pages.

## How settings find the database

With the defaults, Django connects to `localhost:5435`, which is the port the `db`
service publishes on the host. See [Configuration](configuration.md) for every variable
and [Docker](docker.md) for the service definitions.
