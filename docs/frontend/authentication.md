---
id: authentication
title: Authentication and routing
sidebar_position: 1
description: Integration contract for the frontend: registration, login, token refresh, logout, routing by center state and error codes.
---

# Authentication and routing

Contract between the frontend and API v1. Endpoint details:
[REST API](../reference/api.md).

## Tokens

- The API uses JWT in the `Authorization: Bearer <access>` header. No cookies; CORS
  allows no credentials ([ADR 0012](../architecture/decisions/0012-cors-policy.md)).
- **Access token**: 15 minutes. **Refresh token**: 7 days, single use: every refresh
  returns a new pair and blacklists the old refresh token.
- Store the refresh token where the platform keeps secrets best (for example in memory
  plus secure storage on mobile). Never put tokens in URLs.
- Send `Accept-Language` (`ar`, `en` or `fr`) with every request; messages come back in
  that language.

## Flows

**Register an asker** — `POST /api/v1/auth/register/` with `email`, `full_name`,
`password`, `preferred_lang`. A 201 contains `user`, `access` and `refresh`: the user is
logged in.

**Register a center** — `POST /api/v1/auth/register/center/` with the same fields plus a
`center` object (`name` required). A 201 contains `user`, `center` (with
`state: "pending_review"`), `access` and `refresh`. The applicant is the center's admin.

**Log in** — `POST /api/v1/auth/login/` with `email` and `password`. 401
`no_active_account` means wrong credentials or a deactivated account; show one generic
message.

**Refresh** — when a request returns 401 `token_not_valid`, call
`POST /api/v1/auth/refresh/` once with the refresh token, store both new tokens, retry
the request. If refresh also fails with 401, log the user out. Do not refresh in
parallel: the first refresh blacklists the token the others would use.

**Log out** — `POST /api/v1/auth/logout/` with the refresh token (and the access token in
the header), then discard both tokens.

**Throttling** — the four auth endpoints allow 10 requests per minute per client. On 429
`throttled`, wait before retrying (the `Retry-After` header gives seconds).

## Routing after login

Call `GET /api/v1/me/memberships/`. For each active membership, `center.state` decides
the screen:

| `center.state` | Screen |
| --- | --- |
| `pending_review` | "Your center is being reviewed." |
| `rejected` | "Your application was rejected", showing `center.rejection_reason`. |
| `suspended` | "This center is suspended." |
| `operational` | The center dashboard (`GET /api/v1/centers/{slug}/dashboard/`, center admins). |

A user without memberships is an asker. A center endpoint answering 403
`center_not_operational` means the state changed since it was loaded: reload
`me/memberships/`.

## Error codes to handle

| Code | Typical handling |
| --- | --- |
| `not_authenticated`, `token_not_valid` | Refresh once, else go to login. |
| `no_active_account` | Login form error. |
| `email_taken` (field `email`) | "An account already exists": offer login. |
| `password_*` (field `password`) | Show the returned messages under the password field. |
| `center_name_taken`, `invalid_country` (fields under `center`) | Center form errors. |
| `center_not_operational` | Reload memberships and route. |
| `not_center_admin`, `not_center_member` | Hide the action; show "not allowed". |
| `not_found` | Not found page (also for centers the user does not belong to). |
| `user_not_found`, `user_inactive`, `already_member`, `last_center_admin`, `membership_inactive` | Show `detail` next to the member management action. |
| `throttled` | Wait and retry later. |

The full list is in [REST API](../reference/api.md#errors).
