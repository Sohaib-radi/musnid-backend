---
id: 0012-cors-policy
title: "ADR 0012: CORS policy"
sidebar_position: 12
description: Why CORS allows only configured origins, only on /api/, and without credentials.
---

# ADR 0012: CORS policy

## Status

Accepted, 2026-10-04.

## Context

Browser frontends run on other origins than the API and need CORS. The admin must not be
callable cross-origin, and the API does not use cookies.

## Decision

django-cors-headers 4.9.0, with `CorsMiddleware` placed right after
`SecurityMiddleware` so error responses carry CORS headers too:

- `CORS_ALLOWED_ORIGINS` from `DJANGO_CORS_ALLOWED_ORIGINS` (comma-separated); empty by
  default, which disables CORS;
- `CORS_URLS_REGEX = r'^/api/.*$'`: no CORS headers on the admin or anything else;
- `CORS_ALLOW_CREDENTIALS = False`: tokens travel in the `Authorization` header.

## Consequences

- Each frontend origin (including local development ports) must be listed per
  environment.
- No wildcard: a mistyped origin fails closed.
- Cookie-based authentication could not be added without revisiting this decision.
