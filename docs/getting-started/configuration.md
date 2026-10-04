---
id: configuration
title: Configuration
sidebar_position: 3
description: Every environment variable the backend reads, with defaults and parsing rules.
---

# Configuration

All deployment-specific settings come from environment variables. `config/settings.py`
loads `.env` from the repository root with python-dotenv, then reads the variables
through the helpers in `config/env.py`.

## Variables

| Variable | Required | Default | Meaning |
| --- | --- | --- | --- |
| `DJANGO_SECRET_KEY` | Yes | none | Django `SECRET_KEY`: signs sessions, password reset tokens and other signed data. |
| `DJANGO_DEBUG` | No | off | Django `DEBUG`. Enabled only by the exact string `True`. |
| `DJANGO_ALLOWED_HOSTS` | No | empty list | Django `ALLOWED_HOSTS`, comma-separated, for example `localhost,127.0.0.1`. |
| `POSTGRES_DB` | Yes | none | Database name. Also creates the database in the `db` container on first start. |
| `POSTGRES_USER` | Yes | none | Database role. Also creates the role in the `db` container on first start. |
| `POSTGRES_PASSWORD` | Yes | none | Password of that role. |
| `POSTGRES_HOST` | No | `localhost` | Database host. The `web` container overrides it to `db`. |
| `POSTGRES_PORT` | No | `5435` | Database port. The `web` container overrides it to `5432`. |

`.env.example` lists the same variables with comments and is the template for `.env`.

## Parsing rules

- **Empty means unset.** `KEY=` or a value of only spaces is treated as if the variable
  were absent: required variables fail, optional ones take their default. Surrounding
  whitespace is stripped.
- **Missing required variables fail at import time.** Any command that loads settings
  (`manage.py`, gunicorn, tests) stops immediately with
  `django.core.exceptions.ImproperlyConfigured` and a message naming the variable, for
  example `Required environment variable DJANGO_SECRET_KEY is not set.`
- **Booleans are strict.** `DJANGO_DEBUG` is on only for `True`. `true`, `1`, `yes` and
  every other value leave it off, so a typo can never enable debug mode.
- **Lists** are comma-separated; blanks and empty items are dropped.

## Precedence

Variables already set in the process environment win over `.env`
(python-dotenv's default, `override=False`). This is how Docker Compose redirects the
`web` container to the `db` service. A missing `.env` is not an error.

## Writing `.env`

- Generate the secret key with a URL-safe alphabet:
  `python -c "import secrets; print(secrets.token_urlsafe(50))"`.
  Docker Compose interpolates `$` in env files, and a `#` can be read as a comment, so
  Django's own `get_random_secret_key()` (whose alphabet includes both) is not suitable.
- `.env` must never be committed; it is listed in `.gitignore` and `.dockerignore`.

## Fixed settings

These are not configurable through the environment:

| Setting | Value |
| --- | --- |
| Database engine | `django.db.backends.postgresql` (psycopg 3) |
| Extra installed app | `pgvector.django` |
| `STATIC_URL`, `STATIC_ROOT` | `static/`, `staticfiles/` at the repository root |
| `MEDIA_URL`, `MEDIA_ROOT` | `media/`, `media/` at the repository root |
| `TIME_ZONE`, `USE_TZ` | `UTC`, enabled |
