---
id: 0011-api-design
title: "ADR 0011: API design"
sidebar_position: 11
description: The structure of the REST API: versioned paths, public identifiers, thin views, scoped querysets, coded errors and a warning-free OpenAPI schema.
---

# ADR 0011: API design

## Status

Accepted, 2026-10-04.

## Context

Frontends in three languages must react to errors reliably, center data must never leak
across centers, and the business rules already live in `core` services.

## Decision

- **Layout**: app `api` without models; `api/v1/urls.py` with explicit paths; views,
  serializers per area (`auth`, `centers`, `memberships`); settings in `config/api.py`.
  Generic class-based views, no routers: nested center URLs read better as paths.
- **Versioning**: in the path (`/api/v1/`). A breaking change gets `/api/v2/`.
- **Identifiers**: user `uuid`, center `slug`, membership `uuid`; never integer ids.
- **Thin views**: views select querysets and permissions; serializers validate and call
  `core.services`; the rules stay in one place.
- **Scoping**: `CenterScopedMixin.get_center()` looks the slug up among the caller's
  centers only, so non-members get 404 and cannot probe slugs. Permissions then decide
  403 for members: `IsCenterMember`, `IsCenterAdmin`, `IsOperationalCenter`.
- **Errors**: `api/exceptions.py` adds `code` next to `detail` for every single-message
  error and a `codes` map for field errors; domain `ValidationError`s from services become
  400 with their code; every permission has a code. Messages are translated; codes are not.
- **Methods**: `PATCH` for updates; no `PUT`; no `DELETE` (memberships are offboarded).
- **Pagination**: page numbers, 20 per page.
- **Schema**: drf-spectacular; a test runs `spectacular --validate --fail-on-warn`, so
  every endpoint must be annotated well enough to produce no warning. Swagger UI assets
  are self-hosted (drf-spectacular-sidecar).

## Consequences

- Error codes are a public contract: renaming one is a breaking change.
- New center endpoints must use `CenterScopedMixin` to keep the 404 behaviour.
- The schema test makes annotation part of the definition of done.
