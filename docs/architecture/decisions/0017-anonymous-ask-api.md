---
id: 0017-anonymous-ask-api
title: "ADR 0017: Anonymous, synchronous ask API"
sidebar_position: 17
description: Public endpoints to ask questions and read a session's history, answered synchronously, limited per IP and per day.
---

# ADR 0017: Anonymous, synchronous ask API

## Status

Accepted, 2026-10-04. Amended by [ADR 0019](0019-link-questions-to-logged-in-askers.md): authentication is now optional instead of disabled, and a question asked with a valid token is linked to the account.

## Context

The flow of [ADR 0016](0016-question-answering-flow.md) answers a question in 19.8 to
45.6 s (measured on 2026-10-04; 32.2 s in the Docker image, 35.8 s in the last local
run). The competition judges must be able to try the service without signing up, and we
promise not to store personal data. Each answer costs OpenAI tokens (33,068 input and
2,946 output in the last run), so an open endpoint needs limits. The UI must show
each sentence with its source, and a referred question needs a number the asker can
quote when a specialist's reply is attached later.

## Decision

- **Endpoints**: `POST /api/v1/questions/`, `GET /api/v1/questions/?session_id=…` and
  `GET /api/v1/questions/{uuid}/` ([REST API](../../reference/api.md#questions)). Views
  are thin; `AskSerializer` validates and calls `agents.services.ask`.
- **Anonymous**: no login; authentication is disabled on these views so a stale token
  cannot produce a 401. History is grouped by `session_id`, an opaque id of 8 to 64
  characters that the frontend generates. Nothing identifies the asker: no account, no IP
  on `Question`. These endpoints do not act on behalf of a center, so they query
  `Question` by session or uuid, not with `for_center` ([ADR 0005](0005-explicit-center-scoping.md)).
- **Public identifier**: `Question.uuid`. For a referred question it is also the
  follow-up number.
- **Response**: the full answer, and the kept sentences, each with its quote and its
  Bayyinat source (number, title, pages, the book page on dawa.center in the question's
  language, and the PDF at the question's page). The source is the evidence question
  whose text contains the quote, found in code. Notes carry codes (`partial`, `level_c`);
  `verification` counts kept and removed sentences. Kept and dropped sentences are saved
  on `Interaction` (`sentences`, `dropped`) so a drop can be inspected later.
- **Source links**: dawa.center publishes Bayyinat as one page and one Arabic PDF; no
  page per question and no translation were found (2026-10-04). The hosted PDF is
  byte-identical to the ingested file (SHA-256 `619b7201…b410ad4e`, 1,259 pages), and the
  printed page number equals the 0-based PDF index, so `#page=page_start+1` opens the
  question. Both URLs are stored on `SourceDocument` (`url`, `pdf_url`), not in code.
- **Synchronous**: `POST` waits for the answer. Gunicorn runs with `--timeout 120`
  (default 30 s would kill a worker mid-answer), `--workers 3 --threads 2`: six requests
  in flight, so two concurrent questions never wait for each other.
- **Host proxy timeout**: any proxy in front of gunicorn (nginx, a platform load
  balancer) must allow at least 120 s per request; nginx's `proxy_read_timeout`
  defaults to 60 s and would cut long answers.
- **Limits**: per client IP, 5 questions per minute and 50 per day (DRF throttles, scopes
  `ask_minute` and `ask_day`, `POST` only), 429 `throttled`. For the whole service,
  `ASK_DAILY_LIMIT` questions per UTC day (default 150), counted on `Question`; past it
  `ask()` raises before any model call and the API returns 429 `daily_capacity` with a
  fixed, translated "try again tomorrow" reply.
- **Client IP**: `DJANGO_NUM_PROXIES` sets DRF's `NUM_PROXIES` (default 0:
  `REMOTE_ADDR`). DRF's own default trusts the whole, client-controlled
  `X-Forwarded-For`, so the setting is always explicit.
- **Shared cache**: throttle counters live in Django's database cache (table
  `django_cache`, created by `createcachetable`); the default per-process memory cache
  would give each of the 3 workers its own counters. No new service or dependency. Cache
  keys hold a keyed hash (`salted_hmac`) of the IP, never the IP itself.

## Consequences

- Judges can try the demo with no account; the frontend only has to keep a `session_id`.
- A worker thread is held for the whole answer; six concurrent answers is the ceiling
  per container. Moving to asynchronous answers (202 and polling, with a task queue such
  as Celery and Redis) is the path when load or a Telegram bot requires it; that would be
  a new ADR.
- The global limit can be exceeded by at most the requests in flight (six), because the
  count and the save are not locked together.
- Throttle entries stay in `django_cache` until they expire (one day at most); expired
  rows are removed by Django's cache culling, not immediately.
- Anyone holding a `session_id` or a question `uuid` can read those questions. Both are
  unguessable random strings, and questions hold no personal data unless the asker types
  it into the text.
- Sources are looked up by question number in the first ingested document; a second
  source book will need the document recorded with each sentence.
