---
id: 0010-jwt-authentication
title: "ADR 0010: JWT authentication"
sidebar_position: 10
description: Why the API authenticates with short-lived JWT access tokens and rotated, blacklisted refresh tokens identified by the user's uuid.
---

# ADR 0010: JWT authentication

## Status

Accepted, 2026-10-04.

## Context

The API serves web and mobile frontends on other origins. Session cookies would need
CSRF handling and cross-site cookie settings, and do not suit mobile clients. Tokens
must be revocable on logout and must not expose internal integer ids.

## Decision

`djangorestframework_simplejwt` 5.5.1 with its `token_blacklist` app:

- access token 15 minutes, refresh token 7 days;
- `ROTATE_REFRESH_TOKENS` and `BLACKLIST_AFTER_ROTATION`: each refresh returns a new pair
  and blacklists the old refresh token, so a stolen refresh token works at most once;
- logout blacklists the refresh token and requires a valid access token;
- `USER_ID_FIELD = 'uuid'`, claim `user_uuid`: tokens carry the public identifier;
- login with email (case-insensitive, through `UserManager.get_by_natural_key`);
- login, registration and refresh throttled at 10 per minute (scope `auth`).

## Consequences

- An access token stays valid for up to 15 minutes after logout; only refresh tokens
  are revocable.
- The blacklist tables grow with every refresh; expired rows should be purged
  periodically (`flushexpiredtokens`), to be scheduled with deployment.
- Throttling counts in the default cache (local memory per process). With several
  processes, limits apply per process until a shared cache is configured.
- Frontends must refresh one request at a time (see the frontend contract).
