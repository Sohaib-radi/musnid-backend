---
id: 0023-answer-from-telegram
title: "ADR 0023: Linked specialists answer by replying in their center's group"
sidebar_position: 23
description: One-time t.me links connect Telegram accounts; a reply to the bot's notice is saved through revise; updates arrive by polling locally and by webhook in production.
---

# ADR 0023: Linked specialists answer by replying in their center's group

## Status

Accepted, 2026-10-05.

## Context

Centers receive referred questions in their Telegram group
([ADR 0022](0022-telegram-channel.md)), but answering still needs the admin. The goal is
a real interaction: the asker asks on the website, a specialist answers in Telegram, the
asker sees the answer. The target is a private message to each linked specialist, with
the group as a fallback after a timeout; the first step uses the group. The bot must know
who answers: a published answer speaks for the center, so an anonymous group member must
not be able to publish one.

## Decision

- **Only linked specialists answer.** A user links their Telegram account by opening a
  one-time link `https://t.me/<bot>?start=<code>`. The bot receives `/start <code>` and
  saves the sender's Telegram ID in `User.telegram_chat_id` (unique).
  - `TelegramLinkCode` stores the SHA-256 of the code, an expiry (10 minutes) and
    `used_at`; the code is 22 URL-safe characters (`secrets.token_urlsafe(16)`), within
    Telegram's 64-character start parameter.
  - Codes: `telegram_link_invalid` (unknown, used, expired, or deactivated user),
    `telegram_already_linked`, `telegram_link_inactive_user`.
  - Links are created in the admin ("Link a Telegram account": superusers for any user,
    staff for themselves). The center dashboard will show the same link as a QR code.
- **Connecting the group** (one per center): the dashboard's "Connect to Telegram"
  calls `POST centers/{slug}/telegram/connect/` (center admin, operational center), which
  returns a one-time `t.me/<bot>?startgroup=<code>` link (a `TelegramLinkCode` with a
  `center`). Telegram asks which group to add the bot to; the bot receives
  `/start <code>` there and `connect_group` saves the group on the center, linking the
  admin's Telegram account too when it is free. The page polls
  `GET centers/{slug}/telegram/` (`connected`, `me_linked`) behind a spinner.
  - The named constraint `unique_center_telegram_group` keeps a group on one center;
    `connect_group` refuses a taken group (`telegram_group_taken`).
  - `telegram_chat_id` is read-only in the settings API: no one types a group ID.
  - "Disconnect" (`POST centers/{slug}/telegram/disconnect/`, center admin) clears the
    group first, then the bot says goodbye and leaves after the commit, best effort, so a
    Telegram outage never leaves the center connected. Replies to earlier notices in a
    group the center no longer has are ignored.
  - Removing the bot disconnects the center (`my_chat_member` left or kicked); a group
    upgraded to a supergroup keeps its center under the new ID (`migrate_to_chat_id`).
- **Answering**: a reply, in a group, to the bot's sent notice (matched by chat ID and
  `message_id` in `TelegramMessage`) from a linked, active user is saved with
  `qa.services.revise(question, user, text, specialist_answer, note="Telegram")`. The
  asker sees it at once; the referral becomes answered. `revise` keeps its rules: the user
  must be a member of the question's operational center (or staff with the permission).
  The bot confirms in the group, or explains a refusal (not linked, not allowed, not text).
  A second reply adds a new revision; the asker sees the latest.
- **One handler, two transports**: `telegram_bot.updates.handle_update` is fed by
  `telegram_poll` (long polling, local development: Telegram cannot reach a laptop) and by
  `POST /telegram/webhook/` in production. The webhook accepts only requests with
  `TELEGRAM_WEBHOOK_SECRET` in `X-Telegram-Bot-Api-Secret-Token` (compared in constant
  time; 404 otherwise) and answers 200 once an update is handled, even if it failed, so
  Telegram does not resend it forever. `telegram_webhook --set/--delete` registers it.
- The bot needs no admin rights in the group: in privacy mode Telegram still delivers
  replies to the bot's own messages.

## Consequences

- The demo path works end to end without the frontend: the answer appears in
  `GET /api/v1/questions/{uuid}/` (`answered_by: center`, `referral_status: answered`).
- The answer is published as written: no translation yet (the translation crew is
  next), no review step.
- Private messages to linked specialists with a timeout before the group fallback are a
  later step; they reuse the linking and the handler.
- Links are created in the admin for now; an API endpoint for the dashboard comes with
  the dashboard.
