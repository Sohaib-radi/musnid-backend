# Musnid Backend

Backend for the competition "AI Challenge – Serving Islamic Content". Musnid answers
questions about Islam from vetted sources using retrieval-augmented generation (RAG) and
AI agents. Questions the AI must not answer are routed to centers of specialists, who
receive and answer them.

## Documentation

**→ [Full documentation](docs/README.md)**: start there. It has a reading path for
first-time readers and the competition jury, an overview of how a question is answered,
and every page: getting started, architecture and decision records, the RAG pipeline with
measured results, the REST API, the admin, the Telegram bot, frontend integration and
development.

Quick links: [Introduction](docs/intro.md) ·
[How a question is answered](docs/architecture/decisions/0016-question-answering-flow.md) ·
[RAG pipeline](docs/rag/02-pipeline.md) · [REST API](docs/reference/api.md) ·
[Telegram bot](docs/reference/telegram-bot.md) · [Deployment](docs/getting-started/deployment.md) ·
[Sources and credits](docs/sources-and-credits.md)

## Setup

Requirements: Python 3.12 and Docker with Compose v2.

### Local

```bash
python3.12 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install --only-binary=:all: -r requirements.txt

cp .env.example .env        # then set DJANGO_SECRET_KEY and POSTGRES_PASSWORD

docker compose up -d db     # PostgreSQL + pgvector on 127.0.0.1:5435
.venv/bin/python manage.py migrate
.venv/bin/python manage.py test
.venv/bin/python manage.py runserver
```

### Docker

```bash
cp .env.example .env        # if not done yet
docker compose --profile web up -d --build
```

The admin is at http://127.0.0.1:8011/admin/.

## Documentation

See [`docs/`](docs/intro.md), starting with
[Configuration](docs/getting-started/configuration.md) and
[Technology stack](docs/technology-stack.md).
