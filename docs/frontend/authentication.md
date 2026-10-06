---
id: authentication
title: Authentication and routing
sidebar_position: 1
description: Integration contract for the frontend: registration, login, token refresh, logout, routing by center state and error codes.
---

# Authentication and routing

Contract between the frontend
([musnid-frontend](https://github.com/Sohaib-radi/musnid-frontend)) and API v1. Endpoint
details: [REST API](../reference/api.md).

## Tokens

- The API uses JWT in the `Authorization: Bearer <access>` header. No cookies; CORS
  allows no credentials ([ADR 0012](../architecture/decisions/0012-cors-policy.md)).
- **Access token**: 15 minutes. **Refresh token**: 7 days, single use: every refresh
  returns a new pair and blacklists the old refresh token.
- Store the refresh token where the platform keeps secrets best (for example in memory
  plus secure storage on mobile). Never put tokens in URLs.
- Send `Accept-Language` (`ar`, `en` or `fr`) with every request; messages come back in
  that language (except `no_active_account`, see below).
- A browser client calling the API directly needs its origin in
  `DJANGO_CORS_ALLOWED_ORIGINS` ([ADR 0012](../architecture/decisions/0012-cors-policy.md)):
  `http://localhost:3000` locally, the Vercel origin in production
  (`https://api.musnid.online`).

## Flows

**Register an asker** — `POST /api/v1/auth/register/` with `email`, `full_name`,
`password`, `preferred_lang`. A 201 contains `user`, `access` and `refresh`: the user is
logged in.

**Register a center** — `POST /api/v1/auth/register/center/` with the same fields plus a
`center` object (`name` required). A 201 contains `user`, `center` (with
`state: "pending_review"`), `access` and `refresh`. The applicant is the center's admin.

**Log in** — `POST /api/v1/auth/login/` with `email` and `password`. A 200 contains
`access` and `refresh` only, not the user: call `GET /api/v1/me/` with the new access
token to get it (the web frontend does this in its login route). 401
`no_active_account` means wrong credentials or a deactivated account; show one generic
message. Its `detail` comes from SimpleJWT and is not translated, so the client shows its
own translated text for that code.

**Refresh** — when a request returns 401 `token_not_valid`, call
`POST /api/v1/auth/refresh/` once with the refresh token, store both new tokens, retry
the request. If refresh also fails with 401, log the user out. Do not refresh in
parallel: the first refresh blacklists the token the others would use.

**Log out** — `POST /api/v1/auth/logout/` with the refresh token (and the access token in
the header), then discard both tokens.

**Ask while logged in** — `POST /api/v1/questions/` accepts the access token but never
requires it. With a valid token the question is linked to the account and appears in
`GET /api/v1/me/questions/` on every device; with an expired one it is saved
anonymously, without a 401. Refresh the token before asking when the question should be
linked ([ADR 0019](../architecture/decisions/0019-link-questions-to-logged-in-askers.md)).

**Throttling** — the four auth endpoints allow 10 requests per minute per client. On 429
`throttled`, wait before retrying (the `Retry-After` header gives seconds).

## Routing after login

First call `GET /api/v1/me/`. If `is_platform_admin` is true, redirect the whole page to
`admin_url` (the Django admin, where the platform administrator signs in again) and show
no dashboard ([ADR 0024](../architecture/decisions/0024-admin-for-platform-administrators.md)).

Otherwise call `GET /api/v1/me/memberships/`. For each active membership, `center.state` decides
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

## User language

The account's `preferred_lang` (`ar`, `en`, `fr`) is the language the Telegram bot writes
to that user in, on every device. Keep it in step with the site:

| When | Call |
| --- | --- |
| Registration | Send `preferred_lang` set to the current interface language (`POST auth/register/`, `auth/register/center/`; the default is `en`) |
| First load of a tab, or login | `GET /me/` → apply `preferred_lang` as the interface language, once |
| Every language switch while logged in | `PATCH /me/ {"preferred_lang": "ar"}`; the tab keeps the choice |
| The `PATCH` fails | Keep the switched language, show "Language not saved to your account", retry on the next switch or login |

A center's "languages served" is a different setting: what its specialists can handle,
not the language of a user ([Telegram bot](../reference/telegram-bot.md#languages)).

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
