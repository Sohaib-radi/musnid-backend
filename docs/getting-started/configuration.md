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
| `DJANGO_CORS_ALLOWED_ORIGINS` | No | empty list (no CORS) | Origins allowed to call `/api/` from a browser, comma-separated, for example `https://app.example.org,http://localhost:3000` ([ADR 0012](../architecture/decisions/0012-cors-policy.md)). |
| `FIELD_ENCRYPTION_KEYS` | No (yes to store API keys) | empty | Fernet keys, comma-separated, newest first, for secrets stored in the database ([ADR 0014](../architecture/decisions/0014-encrypted-api-keys.md)). Never reuse `DJANGO_SECRET_KEY`. |
| `OPENAI_API_KEY` | No | empty | Fallback OpenAI key when no key is active in the admin. |
| `REFERRAL_LIVE_SECONDS` | No | `60` | Seconds an asker who chose "Ask a specialist now" waits for a live answer; afterwards the question stays in the center's queue. |
| `TELEGRAM_BOT_TOKEN` | No | empty (bot off) | Token of the Telegram bot from @BotFather ([ADR 0022](../architecture/decisions/0022-telegram-channel.md)). Empty: nothing is sent. A secret: never printed or logged. |
| `TELEGRAM_WEBHOOK_SECRET` | No | empty (webhook off) | Secret Telegram sends in `X-Telegram-Bot-Api-Secret-Token` with each update to `/telegram/webhook/` ([ADR 0023](../architecture/decisions/0023-answer-from-telegram.md)); letters, digits, `_` and `-`, up to 256 characters. Empty: the webhook answers 404. Production only; locally run `telegram_poll`. |
| `DJANGO_SITE_URL` | No | empty | Public origin of the backend, such as `https://api.musnid.online`, used to link the admin from Telegram messages. A trailing `/` is removed. Empty: no link. |
| `POSTGRES_DB` | Yes | none | Database name. Also creates the database in the `db` container on first start. |
| `POSTGRES_USER` | Yes | none | Database role. Also creates the role in the `db` container on first start. |
| `POSTGRES_PASSWORD` | Yes | none | Password of that role. |
| `POSTGRES_HOST` | No | `localhost` | Database host. The `web` container overrides it to `db`. |
| `POSTGRES_PORT` | No | `5435` | Database port. The `web` container overrides it to `5432`. |
| `ASK_DAILY_LIMIT` | No | `150` | Questions per UTC day for the whole service; past it `POST /api/v1/questions/` returns 429 `daily_capacity` without calling OpenAI ([ADR 0017](../architecture/decisions/0017-anonymous-ask-api.md)). |
| `DJANGO_NUM_PROXIES` | No | `0` | Proxies in front of the app. `0` uses `REMOTE_ADDR` as the client IP; behind one host proxy set `1`, so per-IP limits read `X-Forwarded-For`. |
| `DJANGO_HTTPS` | No | off | HTTPS behind the host nginx ([ADR 0018](../architecture/decisions/0018-single-vps-deployment.md)). Enabled only by the exact string `True`; it trusts `X-Forwarded-Proto: https`, makes session and CSRF cookies HTTPS-only and redirects HTTP to HTTPS. Leave it off locally. |
| `DJANGO_HSTS_SECONDS` | No | `0` (no header) | Django `SECURE_HSTS_SECONDS`. Set it only after HTTPS works: browsers then refuse plain HTTP to the host for that long. [Deployment](deployment.md) raises it in steps. |

`.env.example` lists the same variables with comments and is the template for `.env`.

## CrewAI switches

CrewAI reads these from the process environment itself. `config/settings.py` sets the
default when a variable is missing or empty, before CrewAI is imported; the Dockerfile
sets the same values in the image.

| Variable | Default | Meaning |
| --- | --- | --- |
| `CREWAI_DISABLE_TELEMETRY` | `true` | Turns off CrewAI's anonymous telemetry. |
| `OTEL_SDK_DISABLED` | `true` | Turns off the OpenTelemetry SDK that CrewAI's telemetry uses. |
| `CREWAI_TRACING_ENABLED` | `false` | Keeps CrewAI's execution tracing off. |

Keep the defaults. These switches do **not** stop CrewAI's first-run prompt "view your
execution traces? [y/N] (20s timeout)" (CrewAI 1.9.3 checks only its user file for that).
`AgentsConfig.ready()` records the decline in that file in every process, before CrewAI
is imported (`agents/tracing.py`). The file is
`appdirs.user_data_dir(<CREWAI_STORAGE_DIR or working directory name>, "CrewAI")/.crewai_user.json`;
if it cannot be written, a warning is logged and the prompt times out after 20 s.

## Parsing rules

- **Empty means unset.** `KEY=` or a value of only spaces is treated as if the variable
  were absent: required variables fail, optional ones take their default. Surrounding
  whitespace is stripped.
- **Missing required variables fail at import time.** Any command that loads settings
  (`manage.py`, gunicorn, tests) stops immediately with
  `django.core.exceptions.ImproperlyConfigured` and a message naming the variable, for
  example `Required environment variable DJANGO_SECRET_KEY is not set.`
- **Booleans are strict.** `DJANGO_DEBUG` and `DJANGO_HTTPS` are on only for `True`. `true`, `1`, `yes` and
  every other value leave them off, so a typo can never enable debug mode.
- **Lists** are comma-separated; blanks and empty items are dropped.
- **Integers** (`ASK_DAILY_LIMIT`, `DJANGO_NUM_PROXIES`, `DJANGO_HSTS_SECONDS`) must be non-negative whole
  numbers; any other value stops the process at startup with `ImproperlyConfigured`.

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
| `CACHES` | Database cache, table `django_cache` (shared by every gunicorn worker; created by `createcachetable`) |
