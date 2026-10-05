---
id: 0019-link-questions-to-logged-in-askers
title: "ADR 0019: Link questions to logged-in askers"
sidebar_position: 19
description: A question asked with a valid access token is linked to the account; asking stays open to anonymous users.
---

# ADR 0019: Link questions to logged-in askers

## Status

Accepted, 2026-10-05. Amends [ADR 0017](0017-anonymous-ask-api.md).

## Context

ADR 0017 made asking anonymous: no account, questions grouped only by a
`session_id` the browser keeps. A user who logs in, or changes device, loses that
history. The next steps let specialists revise answers; a logged-in asker must be able
to see those revisions on their own questions, from any device. Asking must stay open to
anonymous users, and a stale token held by a browser must not block them: the frontend's
client treats a 401 `token_not_valid` as a session to refresh, then sends the user to
the login page.

## Decision

- **`Question.asker`**: a nullable foreign key to the user, `SET_NULL` on delete so
  questions, answers and later reviews survive a deleted account, as anonymous. Index
  `question_asker_recent` (`asker`, `-created_at`).
- **Optional authentication** on the public question endpoints:
  `api.authentication.OptionalJWTAuthentication`, SimpleJWT's authentication that never
  fails. A valid access token identifies the user; no header, an expired, malformed or
  blacklisted token, or a deactivated account leave the request anonymous (no 401).
  ADR 0017 disabled authentication on these views for the same reason; this keeps that
  guarantee while recognizing logged-in users.
- **Saving**: `AskSerializer` passes the authenticated user to `agents.services.ask(...,
  asker=...)`, which stores it on the new `Question`. The `session_id` is still required
  and still saved, so the browser history keeps working for everyone.
- **`GET /api/v1/me/questions/`**: the caller's questions from every session, newest
  first, paginated, in the same shape as the public history. Login required.
- **Not exposed**: the question payload never contains the asker. Staff see the asker's
  email in the admin, where they can also search by it.
- **Not linked retroactively**: questions asked anonymously before logging in stay
  anonymous. Attaching a browser's earlier session to an account is a separate decision.
- **Schema**: `OptionalJWTScheme` (`api/schema.py`) maps the class to the existing
  `jwtAuth` scheme; the `AllowAny` views list "no authentication" as an alternative.

## Consequences

- A logged-in user's questions now hold personal data (the account link). The public
  endpoints still return nothing about the asker; only staff see it in the admin.
- An expired token makes a question anonymous instead of failing: the frontend should
  refresh its token before asking if it wants the question linked.
- Throttling stays per IP address; a logged-in user has the same limits as anyone.
- Migration `qa.0003_question_asker` adds a nullable column and an index: no data change.
