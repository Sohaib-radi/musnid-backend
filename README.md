# Musnid Backend

Backend for the competition "AI Challenge – Serving Islamic Content". Musnid answers
questions about Islam from vetted sources using retrieval-augmented generation (RAG) and
AI agents. Questions the AI must not answer are routed to centers of specialists, who
receive and answer them.

## Access for the jury

| What | Where |
| --- | --- |
| Website | [www.musnid.online](https://www.musnid.online) |
| Admin (platform administrator) | [api.musnid.online/admin](https://api.musnid.online/admin/) |
| Admin login and password | In the submission form, field **«وصف المشروع»** of **«بيانات تسليم التحكيم النهائي»** (not published in this repository) |
| API documentation | [api.musnid.online/api/docs](https://api.musnid.online/api/docs/) |

> [!IMPORTANT]
> **Crucial before using a center on the website or testing the Telegram bot: approve it.**
> A center registered on the website stays *pending review*: its center admin cannot use
> the center dashboard (settings, specialists, questions, Telegram connection), and it
> receives nothing. A platform administrator must **approve** it in the admin. To test
> the Telegram bot, also tick **"Also make it the default center"**: only the default
> center receives the questions askers send to specialists, so only its linked
> specialists get them in Telegram.
> **→ [Step-by-step guide with screenshots: Approve a center](docs/guides/approve-a-center.md)**

<p align="center">
  <a href="docs/guides/approve-a-center.md"><img src="docs/images/admin/centers-list-approve.png" alt="Centers list in the admin: a pending center with its Approve button" width="49%"></a>
  <a href="docs/guides/approve-a-center.md"><img src="docs/images/admin/center-approve-dialog.png" alt="Approve dialog with &quot;Also make it the default center&quot; ticked" width="49%"></a>
  <br><em>1. Click <strong>Approve</strong> on the pending center · 2. Tick <strong>Also make it the default center</strong>, then <strong>Approve</strong></em>
</p>

## Related repository

The website (asking, dashboards, Telegram connection) is in
**[musnid-frontend](https://github.com/Sohaib-radi/musnid-frontend)**; this repository is
its API and admin.

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
