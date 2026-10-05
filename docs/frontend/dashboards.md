---
id: dashboards
title: Dashboards API
sidebar_position: 2
description: The endpoints the frontend needs for the user dashboard and the center dashboard, with example payloads, and what is not available yet.
---

# Dashboards API

What the frontend calls to build the **user dashboard** and the **center dashboard**.
Only endpoints that exist today are described; the last section lists what is not
available yet, so it is not built against.

Login, tokens and routing by center state: [Authentication and routing](authentication.md).
Every field and error: [REST API](../reference/api.md). Types: `npm run api:types` from
`/api/schema/`.

## Basics

| Item | Value |
| --- | --- |
| Base URL | `http://localhost:8000/api/v1/` locally (CORS allows `http://localhost:3000`) |
| Auth | `Authorization: Bearer <access>`; on 401 `token_not_valid`, refresh once, then log out |
| Language | `Accept-Language: ar`, `en` or `fr`; messages follow it, codes never change |
| Lists | `{"count", "next", "previous", "results"}`, 20 per page, `?page=N` |
| Errors | `{"detail", "code"}`, or field errors `{"<field>": [...], "codes": {"<field>": [...]}}`; branch on `code` |
| Updates | `PATCH` only; no `PUT`, no `DELETE` |

## Who sees which dashboard

Call `GET me/` after login: if `is_platform_admin` is true, redirect the whole page to
`admin_url` (the Django admin) and stop. Otherwise call `GET me/memberships/`:

| Memberships | Dashboard |
| --- | --- |
| None | User dashboard only |
| Active, role `specialist` | User dashboard + read-only center page |
| Active, role `center_admin`, `center.state = operational` | Center dashboard |
| Active, `center.state` `pending_review` / `rejected` / `suspended` | A status page (show `rejection_reason` when rejected) |

## User dashboard

### Profile

`GET me/`

```json
{
  "uuid": "6b0f…",
  "email": "amina@example.com",
  "full_name": "Amina",
  "preferred_lang": "fr",
  "avatar": null,
  "is_verified": false,
  "telegram_linked": false,
  "is_platform_admin": false,
  "admin_url": null
}
```

`PATCH me/` with `{"full_name": "…", "preferred_lang": "ar"}` returns the profile. Other
fields are read-only.

### My questions

`GET me/questions/`: questions asked while logged in, newest first, from any device.

```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "uuid": "b4c5…",
      "text": "Puis-je combiner les prières en voyage… ?",
      "language": "fr",
      "level": "D",
      "decision": "refer",
      "answer": "Oui, selon l'avis majoritaire…",
      "answered_by": "center",
      "review": {"center": "Al Mouajih", "revised_at": "2026-10-05T13:22:15Z"},
      "sentences": [],
      "notes": [],
      "verification": {"kept": 0, "removed": 0},
      "follow_up_number": "b4c5…",
      "referral_status": "answered",
      "created_at": "2026-10-05T13:20:02Z"
    }
  ]
}
```

| Show | From |
| --- | --- |
| Badge "Answered by the AI" / "Answered by <center>" | `answered_by` (`ai` / `center`), `review.center` |
| Badge "Waiting for a specialist" | `referral_status` `open` or `in_progress` |
| Badge "Answered by a specialist" | `referral_status` `answered` |
| "Closed without an answer" | `referral_status` `closed` |
| Sources under each sentence | `sentences[].source` (empty when a center answered) |

A waiting question changes when a specialist answers: refetch `GET questions/{uuid}/`
(for example every 30 seconds while `referral_status` is `open` or `in_progress`).

### My centers

`GET me/memberships/`

```json
{
  "count": 1, "next": null, "previous": null,
  "results": [
    {
      "uuid": "1d2e…",
      "role": "center_admin",
      "is_active": true,
      "created_at": "2026-10-01T09:00:00Z",
      "left_at": null,
      "center": {
        "slug": "al-mouajih",
        "name": "Al Mouajih",
        "country": {"code": "MA", "name": "Morocco"},
        "description": "…",
        "contact_email": "contact@example.com",
        "website": "",
        "logo": null,
        "languages": ["ar", "en", "fr"],
        "status": "approved",
        "state": "operational",
        "rejection_reason": "",
        "is_active": true,
        "created_at": "2026-10-01T09:00:00Z"
      }
    }
  ]
}
```

## Center dashboard

All endpoints below: center admin of an operational center. Errors: 403
`not_center_admin` or `center_not_operational`, 404 for non-members.
`GET centers/{slug}/` works for any active member in any state (for specialists and
status pages).

### Overview

`GET centers/{slug}/dashboard/`

```json
{
  "center": {"slug": "al-mouajih", "name": "Al Mouajih", "state": "operational", "…": "…"},
  "members": {"total": 4, "center_admins": 1, "specialists": 3}
}
```

### Settings

`GET centers/{slug}/settings/` and `PATCH centers/{slug}/settings/`

```json
{
  "slug": "al-mouajih",
  "name": "Al Mouajih",
  "country": {"code": "MA", "name": "Morocco"},
  "description": "…",
  "contact_email": "contact@example.com",
  "website": "",
  "telegram_chat_id": -5575290607,
  "languages": ["ar", "en", "fr"]
}
```

Editable: `country` (ISO code, list from `GET countries/`), `description`,
`contact_email`, `website`, `languages`. `slug`, `name` and `telegram_chat_id` are
read-only: the group is connected only through the bot (next section).

### Connect to Telegram

One Telegram group per center; a group serves one center only.

| Step | Frontend | Call |
| --- | --- | --- |
| 1 | Button "Connect to Telegram" (center admin) | `POST centers/{slug}/telegram/connect/` → 201 `{"url", "expires_at"}` |
| 2 | Open `url` in a new tab (`https://t.me/<bot>?startgroup=…`); Telegram asks which group to add the bot to | |
| 3 | Show a spinner; every 2 seconds | `GET centers/{slug}/telegram/` → `{"connected": false, "me_linked": false}` |
| 4 | When `connected` is `true`: stop, show "Connected" | the bot also confirms in the group |
| 5 | When `expires_at` passes before that (10 minutes): stop, offer "Try again" | |

The admin who adds the bot is linked at the same time (`me_linked: true`), so they can
answer from the group at once. `GET centers/{slug}/telegram/` works for any member: show
"Connected" / "Not connected" on page load. If the bot is removed from the group,
`connected` becomes `false`.

**Disconnect** (center admin): a "Disconnect" button next to "Connected", with a
confirmation ("Referred questions will no longer arrive in Telegram"), calls
`POST centers/{slug}/telegram/disconnect/` → 200 `{"connected": false, "me_linked": …}`.
Show "Connect to Telegram" again. The bot says goodbye in the group and leaves it; the
center is disconnected even if Telegram cannot be reached. Calling it on a center without a
group also returns 200.

| Error | Meaning |
| --- | --- |
| 403 `not_center_admin`, `center_not_operational` | Only admins of an approved, active center connect or disconnect. |
| 503 `telegram_unavailable` | The bot is off or Telegram cannot be reached; retry later. |

### Specialists (memberships)

| Action | Call | Body | Errors to show |
| --- | --- | --- | --- |
| List | `GET centers/{slug}/memberships/` | | |
| Add | `POST centers/{slug}/memberships/` | `{"email": "…", "role": "specialist"}` | `user_not_found` (the person must register first), `user_inactive`, `already_member` |
| Change role | `PATCH centers/{slug}/memberships/{uuid}/` | `{"role": "center_admin"}` | `last_center_admin`, `membership_inactive` |
| Remove | `POST centers/{slug}/memberships/{uuid}/offboard/` | | `last_center_admin`, `membership_inactive` |

A membership in the list:

```json
{
  "uuid": "9a8b…",
  "user": {"uuid": "6b0f…", "email": "amina@example.com", "full_name": "Amina"},
  "role": "specialist",
  "is_active": true,
  "created_at": "2026-10-02T10:00:00Z",
  "left_at": null
}
```

Roles: `specialist`, `center_admin`. Removed members stay in the list with
`is_active: false` and `left_at`.

## Telegram for each specialist

Every member of an operational center connects their own Telegram; questions for their
center then arrive in their private chat with the bot, with a "✍️ Answer" button.

| Step | Call |
| --- | --- |
| On load | `GET me/` → `telegram_linked` |
| "Connect Telegram" | `POST me/telegram/link/` → open `url`; spinner polling `GET me/` every 2 s until `telegram_linked` is true, or `expires_at` passes |
| "Disconnect" | `POST me/telegram/unlink/` |

The group flow above is optional and can stay hidden.

## Asking a specialist (asker side)

When `can_ask_specialist` is true, show `answer` (it says why the AI does not answer) and
two buttons; each calls `POST questions/{uuid}/specialist/` with
`{"mode": "live" | "ticket", "session_id": "…"}`:

| Mode | Then |
| --- | --- |
| `live` ("Ask a specialist now") | Countdown to `referral_live_until`, poll every 5 s; at 0, "the center will answer you here", poll every 60 s |
| `ticket` ("Save as a ticket") | "Your ticket was saved", poll every 60 s while the page is open |

`referral_status` `answered` → show `answer`, "Answered by `review.center`".

## Not available yet

Do not build against these; they come in the next backend steps.

| Feature | Status |
| --- | --- |
| Referred questions of the center (queue, assign, close, answer) | Admin only for now. |
| Telegram link (QR code) for each specialist | Admin only for now ("Link a Telegram account"). The admin who connects the group is linked automatically; `telegram_linked` in `GET me/` and `me_linked` show the result. |
| Statistics (questions per day, answer times) | Not started. |
| Logo and avatar upload | Fields exist, read-only in the API. |
