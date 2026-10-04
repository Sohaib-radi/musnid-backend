---
id: api
title: REST API
sidebar_position: 3
description: Every endpoint of API v1, who can call it, its request, response and error codes.
---

# REST API

Base path `/api/v1/`. Live schema: `/api/schema/` (OpenAPI 3); interactive docs:
`/api/docs/`. Design: [ADR 0011](../architecture/decisions/0011-api-design.md);
authentication: [ADR 0010](../architecture/decisions/0010-jwt-authentication.md).

## Conventions

- **Authentication**: `Authorization: Bearer <access token>`. Every endpoint requires it
  unless marked public.
- **Identifiers**: only public ones appear: user `uuid`, center `slug`, membership `uuid`.
- **Language**: messages follow `Accept-Language` (`ar`, `en`, `fr`). Codes never change.
- **Pagination**: lists return `count`, `next`, `previous`, `results`; 20 per page,
  `?page=N`.
- **Methods**: updates use `PATCH`. There is no `PUT` and no `DELETE`.
- **Throttling**: register, register/center, login and refresh share the `auth` scope:
  10 requests per minute per client. The 11th returns 429 `throttled`.

## Errors

| Shape | When |
| --- | --- |
| `{"detail": "<text>", "code": "<code>"}` | Any single-message error: 401, 403, 404, 405, 429, and 400 from a business rule. |
| `{"<field>": ["<text>"], "codes": {"<field>": ["<code>"]}}` | Field validation (400). Nested fields nest the same way. |

Clients branch on `code`, never on the text.

| Code | Status | Meaning |
| --- | --- | --- |
| `not_authenticated` | 401 | No or malformed token. |
| `token_not_valid` | 401 | Expired, invalid or blacklisted token. |
| `no_active_account` | 401 | Wrong email or password, or inactive account (login). |
| `not_center_member` | 403 | Not an active member of the center. |
| `not_center_admin` | 403 | Member, but not a center admin. |
| `center_not_operational` | 403 | Center pending review, rejected or suspended. |
| `not_found` | 404 | Unknown resource, or a center the caller does not belong to. |
| `method_not_allowed` | 405 | E.g. `PUT` or `DELETE`. |
| `throttled` | 429 | Too many auth requests. |
| `email_taken` | 400 (field) | Registration with an existing email (any case). |
| `password_too_short`, `password_too_common`, `password_entirely_numeric`, `password_too_similar` | 400 (field `password`) | Django password validators. |
| `center_name_taken`, `invalid_country` | 400 (field `center.name`, `center.country`) | Center registration. |
| `invalid_choice` | 400 (field) | Value outside the allowed choices. |
| `user_not_found`, `user_inactive`, `already_member`, `invalid_role` | 400 | Adding a member. |
| `last_center_admin`, `membership_inactive` | 400 | Changing a role or offboarding. |

## Auth

| Method and path | Who | Request | Response |
| --- | --- | --- | --- |
| `POST auth/register/` | public, throttled | `email`, `full_name`, `password`, `preferred_lang` (optional, default `en`) | 201 `{"user", "access", "refresh"}` |
| `POST auth/register/center/` | public, throttled | the same, plus `center`: `name`, `country` (ISO code), `description`, `contact_email`, `website`, `languages` | 201 `{"user", "center", "access", "refresh"}`; the center is `pending_review` and the caller its center admin |
| `POST auth/login/` | public, throttled | `email` (any case), `password` | 200 `{"access", "refresh"}` |
| `POST auth/refresh/` | public, throttled | `refresh` | 200 `{"access", "refresh"}`; the old refresh token is blacklisted |
| `POST auth/logout/` | authenticated | `refresh` | 200 `{}`; the refresh token is blacklisted |

Token lifetimes: access 15 minutes, refresh 7 days. Tokens identify the user by the
claim `user_uuid`.

## Me

| Method and path | Who | Request | Response |
| --- | --- | --- | --- |
| `GET me/` | authenticated | | `uuid`, `email`, `full_name`, `preferred_lang`, `avatar`, `is_verified`, `telegram_linked` |
| `PATCH me/` | authenticated | `full_name`, `preferred_lang` (others are read-only) | the profile |
| `GET me/memberships/` | authenticated | | paginated memberships, active first: `uuid`, `role`, `is_active`, `created_at`, `left_at`, `center` (a center, below) |

## Centers

A center: `slug`, `name`, `country` (`{"code", "name"}` or null), `description`,
`contact_email`, `website`, `logo`, `languages`, `status`
(`pending`/`approved`/`rejected`), `state`, `rejection_reason`, `is_active`, `created_at`.

`state` is what the frontend routes on: `pending_review`, `rejected`, `suspended`
(approved but inactive) or `operational`.

| Method and path | Who | Response | Errors |
| --- | --- | --- | --- |
| `GET centers/{slug}/` | any active member, any state | a center | 404 for non-members |
| `GET centers/{slug}/dashboard/` | center admin, operational center | `{"center", "members": {"total", "center_admins", "specialists"}}` | 403 `not_center_admin`, `center_not_operational`; 404 |
| `GET centers/{slug}/settings/` | center admin, operational center | `slug`, `name`, `country`, `description`, `contact_email`, `website`, `telegram_chat_id`, `languages` | as above |
| `PATCH centers/{slug}/settings/` | same | any of `country`, `description`, `contact_email`, `website`, `telegram_chat_id`, `languages`; `slug` and `name` are read-only | as above; 400 field errors |
| `GET countries/` | public | `[{"code", "name"}]`, names in the request language | |

## Memberships

All: center admin of an operational center (403 `not_center_admin`,
`center_not_operational`; 404 for non-members and for memberships of other centers).

| Method and path | Request | Response | Business errors (400) |
| --- | --- | --- | --- |
| `GET centers/{slug}/memberships/` | | paginated, active first: `uuid`, `user` (`uuid`, `email`, `full_name`), `role`, `is_active`, `created_at`, `left_at` | |
| `POST centers/{slug}/memberships/` | `email` (any case), `role` | 201 membership | `user_not_found`, `user_inactive`, `already_member` |
| `GET centers/{slug}/memberships/{uuid}/` | | membership | |
| `PATCH centers/{slug}/memberships/{uuid}/` | `role` | membership | `last_center_admin`, `membership_inactive` |
| `POST centers/{slug}/memberships/{uuid}/offboard/` | | membership (inactive, `left_at` set) | `last_center_admin`, `membership_inactive` |

Memberships are never deleted (405 for `DELETE`).
