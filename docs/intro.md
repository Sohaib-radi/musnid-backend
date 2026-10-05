---
id: intro
title: Introduction
sidebar_position: 1
description: Purpose of the Musnid backend and the current state of the implementation.
---

# Musnid backend

Musnid is the backend for the competition "AI Challenge – Serving Islamic Content". It
answers questions about Islam from vetted sources using retrieval-augmented generation
(RAG) and AI agents. Questions the AI must not answer are routed to centers of
specialists, who receive and answer them.

This documentation is reference material for engineers working on the backend. It is
written as Docusaurus content; this repository holds the Markdown only.

## Current status

| Area | Status | Notes |
| --- | --- | --- |
| Project skeleton | Done | Django 6.0 project `config`, app `core`. |
| Configuration | Done | Environment variables, optional `.env`; see [Configuration](getting-started/configuration.md). |
| Database | Done | PostgreSQL 17 with pgvector, via Docker Compose on port 5435. |
| Docker | Done | `db` service always; `web` service (gunicorn) under the `web` profile on port 8011. |
| Domain models | Done | `User` (email login), `Center` (single default), `Membership` (roles, history); see [Models](reference/models.md). |
| Center scoping | Done | Explicit `for_center()`; see [Tenancy](architecture/tenancy.md). |
| Membership rules | Done | `add_member`, `change_role`, `offboard`; a center keeps one active admin. |
| Tests | Done | 428 tests against a real PostgreSQL test database; see [Testing](development/testing.md). |
| Static files in Docker | Done | WhiteNoise serves them from gunicorn ([ADR 0018](architecture/decisions/0018-single-vps-deployment.md)). |
| Internationalisation (Arabic, French) | Done | Project catalog 105 strings and Unfold vendor catalog 131 strings, fully translated and enforced by tests; see [Translations](development/translations.md). |
| Admin | Done | Unfold theme with the Musnid brand, sidebar, language switcher; users, centers, memberships, groups, and every asked question with its AI answer (read-only); see [Admin](reference/admin.md). |
| REST API | Done | JWT auth, registration of askers and centers, profile, centers, memberships, countries; OpenAPI at `/api/docs/`; see [REST API](reference/api.md) and [Frontend](frontend/authentication.md). |
| Provider API keys | Done | Encrypted OpenAI keys managed in the admin; see [Provider API keys](reference/api-keys.md). |
| Knowledge base (RAG) | Done | Bayyinat extracted (263 questions), 1,432 chunks embedded, search and evidence; see [RAG](rag/01-extraction-findings.md). |
| Question answering (agents) | Done | CrewAI flow: classify, route, retrieve, write, verify with quotes, decide; fixed replies; every question recorded ([ADR 0016](architecture/decisions/0016-question-answering-flow.md)). |
| Ask API | Done | `POST /api/v1/questions/`, anonymous or linked to the account when logged in ([ADR 0019](architecture/decisions/0019-link-questions-to-logged-in-askers.md)), `GET /api/v1/me/questions/`, with sentences linked to their Bayyinat source, session history, per-IP and daily limits; synchronous ([ADR 0017](architecture/decisions/0017-anonymous-ask-api.md), [REST API](reference/api.md#questions)). |
| Deployment | Done | Live at `https://api.musnid.online` on one VPS since 2026-10-05; see [Deployment](getting-started/deployment.md). |
| Answer revisions | Done | Specialists and staff revise answers in the admin through `qa.services.revise`; the asker sees the latest revision under the center's name, the AI answer stays for audit ([ADR 0020](architecture/decisions/0020-answer-revisions.md)). |
| Referral tickets | Done | A referred question opens a ticket for its center (open, in progress, answered, closed); assigned and closed in the admin through `qa.services`, marked answered by a revision; the asker sees `referral_status` ([ADR 0021](architecture/decisions/0021-referral-tickets.md)). |
| Telegram | Done | A referred question is posted to its center's Telegram group; a linked specialist replies to it and the asker sees the answer at once ([ADR 0022](architecture/decisions/0022-telegram-channel.md), [ADR 0023](architecture/decisions/0023-answer-from-telegram.md)). Translation and private messages with a group fallback are next. |
| Center review | Done | Self-registered centers start pending; staff approve or reject in the admin ([ADR 0013](architecture/decisions/0013-center-registration-with-review.md)). |

## Production: current use and limits

The backend is live at `https://api.musnid.online`, but for now it is used only by the
developer; the Vercel frontend is not connected yet. The limits below fit that stage and
must be reviewed before the frontend goes public and the judges start testing.

| Limit | Current value | Where |
| --- | --- | --- |
| Questions per day, whole service | 150, then 429 `daily_capacity` without calling OpenAI | `ASK_DAILY_LIMIT` in the server's `.env` |
| Questions per IP address | 5 per minute and 50 per day | `ask_minute` and `ask_day` in `config/api.py` |
| Logins, registrations and token refreshes per IP address | 10 per minute | `auth` in `config/api.py` |
| Browser origins allowed (CORS) | none: a browser frontend is blocked until its origin is listed | `DJANGO_CORS_ALLOWED_ORIGINS` |
| OpenAI spending | no limit on the account yet | OpenAI account, Billing → Limits |
| Concurrent answers | 6 (3 gunicorn workers × 2 threads), 120 s timeout each | `Dockerfile`, `docker-compose.yml` |

Planned once the frontend is integrated, if time allows (details in
[Deployment → To do](getting-started/deployment.md#to-do)): CORS for the Vercel origin,
an OpenAI spending limit with a matching daily limit, daily database backups, an uptime
alert, and HSTS.

## Where to go next

- [Local development](getting-started/local-development.md): run the project on your machine.
- [Docker](getting-started/docker.md): run the database and the application in containers.
- [Configuration](getting-started/configuration.md): every environment variable.
- [Deployment](getting-started/deployment.md): the production VPS, step by step.
- [Technology stack](technology-stack.md): dependencies, versions and licenses.
- [Models](reference/models.md) and [Data model](architecture/data-model.md).
- [Tenancy](architecture/tenancy.md): how data is scoped to centers.
- [Admin](reference/admin.md): every admin page and the sidebar.
- [REST API](reference/api.md) and the [frontend contract](frontend/authentication.md).
- [Decision records](architecture/decisions/0001-python-3-12.md): ADR 0001 to 0023.
