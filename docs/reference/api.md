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
- **Identifiers**: only public ones appear: user `uuid`, center `slug`, membership `uuid`,
  question `uuid`.
- **Language**: messages follow `Accept-Language` (`ar`, `en`, `fr`). Codes never change.
- **Pagination**: lists return `count`, `next`, `previous`, `results`; 20 per page,
  `?page=N`.
- **Methods**: updates use `PATCH`. There is no `PUT` and no `DELETE`.
- **Throttling**: register, register/center, login and refresh share the `auth` scope:
  10 requests per minute per client. The 11th returns 429 `throttled`. Asking has its own
  limits (see [Questions](#questions)).

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
| `throttled` | 429 | Too many auth requests, or too many questions from one IP. |
| `telegram_unavailable` | 503 | The Telegram bot is off or Telegram cannot be reached. |
| `daily_capacity` | 429 | The service's daily limit of questions is reached; `detail` is a fixed "try again tomorrow" reply. |
| `unavailable` | 503 | A question cannot be saved (no default center configured). |
| `session_required` | 400 | History requested without `session_id`. |
| `min_length`, `max_length`, `required`, `invalid` | 400 (field) | Question `text` (3 to 2,000 characters) or `session_id` (8 to 64 of `A-Z a-z 0-9 - _`). |
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
| `GET me/` | authenticated | | `uuid`, `email`, `full_name`, `preferred_lang`, `avatar`, `is_verified`, `telegram_linked`, `is_platform_admin` (superuser), `admin_url` (the admin's address for a platform administrator, else null; [ADR 0024](../architecture/decisions/0024-admin-for-platform-administrators.md)) |
| `PATCH me/` | authenticated | `full_name`, `preferred_lang` (others are read-only) | the profile |
| `POST me/telegram/link/` | authenticated | | 201 `{"url", "expires_at"}`: a one-time `t.me/<bot>?start=` link that links the caller's Telegram ("Connect Telegram"); 503 `telegram_unavailable` |
| `POST me/telegram/unlink/` | authenticated | | `{"telegram_linked": false}` |
| `GET me/questions/` | authenticated | | paginated questions the caller asked while logged in, newest first, in the question shape ([Questions](#questions)) |
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
| `PATCH centers/{slug}/settings/` | same | any of `country`, `description`, `contact_email`, `website`, `languages`; `slug`, `name` and `telegram_chat_id` are read-only (the group is connected through the bot) | as above; 400 field errors |
| `POST centers/{slug}/telegram/connect/` | center admin, operational center | 201 `{"url", "expires_at"}`: a one-time `t.me/<bot>?startgroup=` link, valid 10 minutes ([ADR 0023](../architecture/decisions/0023-answer-from-telegram.md)) | 403 as above; 503 `telegram_unavailable` |
| `POST centers/{slug}/telegram/disconnect/` | center admin, operational center | 200 `{"connected": false, "me_linked"}`; clears the group; the bot says goodbye and leaves (best effort) | 403 as above |
| `GET centers/{slug}/telegram/` | any active member, operational center | `{"connected", "me_linked"}`; polled while connecting | 403 `center_not_operational`; 404 |
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

## Questions

Public: no login needed ([ADR 0017](../architecture/decisions/0017-anonymous-ask-api.md)).
Authentication is optional and never fails (`OptionalJWTAuthentication`): with a valid
access token, a new question is linked to the account
([ADR 0019](../architecture/decisions/0019-link-questions-to-logged-in-askers.md)); without
one, or with an expired or invalid one, the request is anonymous, never a 401. The
payload never contains the asker. Questions are grouped by `session_id`, an opaque id the
frontend generates (for example a random UUID kept in local storage).

| Method and path | Request | Response |
| --- | --- | --- |
| `POST questions/` | `text` (3 to 2,000 characters), `session_id` | 201 question; waits for the answer (19.8 to 45.6 s measured) |
| `GET questions/?session_id=…` | | paginated, newest first |
| `GET questions/{uuid}/` | | question |
| `POST questions/{uuid}/specialist/` | `mode` (`live` or `ticket`), `session_id` (anonymous askers) | 201 question; sends a question the AI did not answer (`refer` or `abstain`) to the specialists. Only the asker (404 otherwise); 400 `not_referable`, `referral_exists`; throttled like asking |
| `GET me/questions/` | login required | the caller's questions from every session, paginated, newest first |

There is no `PUT`, `PATCH` or `DELETE` (405).

Question:

```json
{
  "uuid": "9b2e4c1a-…",
  "session_id": "3f1c9a2e-…",
  "text": "هل انتشر الإسلام بالسيف؟",
  "language": "ar",
  "level": "B",
  "decision": "answer",
  "answer": "… [Q229]. …\n\n<notes>",
  "answered_by": "ai",
  "review": null,
  "sentences": [
    {
      "text": "<sentence without [Q<n>] markers>",
      "quote": "<supporting quote from the book, Arabic>",
      "source": {
        "number": 229,
        "title": "هل انتشَرَ الإسلامُ بالسيف؟",
        "pages": {"start": 1074, "end": 1081},
        "url": "https://dawa.center/file/7937?lang=ar",
        "pdf_url": "https://dawa.center/storage/files/….pdf#page=1075"
      }
    }
  ],
  "notes": [{"code": "partial", "text": "…"}, {"code": "level_c", "text": "…"}],
  "verification": {"kept": 4, "removed": 1},
  "follow_up_number": null,
  "referral_status": null,
  "created_at": "2026-10-04T17:30:00Z"
}
```

| Field | Meaning |
| --- | --- |
| `language` | `ar`, `en` or `fr`; empty if classification failed. |
| `level` | `A`, `B`, `C`, `D` or `out_of_scope`; `null` if classification failed. |
| `decision` | `answer`, `partial`, `refer`, `abstain` or `out_of_scope`. |
| `answer` | The full text shown to the asker, with `[Q<n>]` markers and the notes. For `refer`, `abstain` and `out_of_scope` it is the fixed reply. When a specialist revised it, the latest revision's plain text. |
| `answered_by` | `ai`, or `center` when a specialist revised the answer ([ADR 0020](../architecture/decisions/0020-answer-revisions.md)). |
| `review` | `null`, or `{"center": <center name>, "revised_at": <date>}` for a revised answer. The specialist's name is never returned. |
| `sentences` | Each kept sentence with its quote and its source; empty when the answer was revised. The source is the evidence question whose text contains the quote, found in code. Empty for fixed replies. |
| `source.url` | The book's page on dawa.center, interface in the question's language. The book is published as one Arabic PDF; there is no page per question. |
| `source.pdf_url` | The same PDF as the knowledge base (SHA-256 checked), opened at the question's first page. |
| `notes` | Empty when the answer was revised. Otherwise, fixed notes after an answer: `partial` (the sources answer only in part), `level_c` (scholarly disagreement). Clients style them by `code`. |
| `verification` | Number of sentences kept and removed by the quote and entailment checks. |
| `follow_up_number` | For `refer`: the question's `uuid`, to quote when the specialist's reply is attached later. `null` otherwise. |
| `can_ask_specialist` | True when the AI did not answer and the question was not sent yet: show "Ask a specialist now" and "Save as a ticket". |
| `referral_mode` | `live` or `ticket`; null when not sent. |
| `referral_live_until` | For a live request: end of the 1-minute live window (`REFERRAL_LIVE_SECONDS`); null otherwise. |
| `referral_status` | For `refer`: where the center's ticket stands, `open`, `in_progress`, `answered` or `closed` (closed without an answer) ([ADR 0021](../architecture/decisions/0021-referral-tickets.md)). `null` otherwise. |

Limits on `POST`:

| Limit | Response |
| --- | --- |
| 5 per minute and 50 per day per client IP (`ask_minute`, `ask_day`) | 429 `throttled` |
| `ASK_DAILY_LIMIT` questions per UTC day for the whole service (default 150) | 429 `daily_capacity`, nothing saved, no model call |

The client IP is `REMOTE_ADDR`, or the address `DJANGO_NUM_PROXIES` hops from the end of
`X-Forwarded-For` behind a proxy ([Configuration](../getting-started/configuration.md)).
Reading the history is not throttled.

