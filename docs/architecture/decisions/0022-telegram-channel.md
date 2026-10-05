---
id: 0022-telegram-channel
title: "ADR 0022: A Telegram bot notifies centers of referred questions"
sidebar_position: 22
description: The telegram_bot app, a minimal Bot API client over httpx, a referral_opened signal and a log of every message sent.
---

# ADR 0022: A Telegram bot notifies centers of referred questions

## Status

Accepted, 2026-10-05.

## Context

Referred questions now open a ticket ([ADR 0021](0021-referral-tickets.md)), but a
center learns about it only by opening the admin. Specialists work in Telegram groups;
`Center.telegram_chat_id` already holds the group of each center. The bot must notify
the group first; later steps add a webhook, account linking, answering from the group
and translation between the asker's and the specialist's languages. A Telegram outage
must never turn an asker's answer into an error.

## Decision

- **A separate app, `telegram_bot`**: a channel like `api`, holding no business rule;
  it calls `qa.services`. Not named `telegram`, the import name of the main Telegram
  library.
- **No new dependency**: `telegram_bot.client.TelegramClient` calls the Bot API over
  `httpx` (already installed), with a 5-second timeout. Frameworks such as
  python-telegram-bot or aiogram are asynchronous and built around their own update
  loop, which a synchronous Django project does not need for HTTPS calls.
- **Token**: `TELEGRAM_BOT_TOKEN` in the environment, one per deployment; empty turns
  the bot off. It is part of every request URL, so errors never carry the URL:
  `TelegramError` holds Telegram's own description, or the exception type of a network
  failure, raised `from None`. The test runner empties the token in every process.
- **Decoupling**: `qa.services.open_referral` sends `qa.signals.referral_opened` with
  `send_robust` once the transaction commits; `telegram_bot.receivers` posts the notice.
  `qa` does not import Telegram, and other channels can listen to the same signal.
- **Notice**: in the center's first language (`Center.languages`, else
  `LANGUAGE_CODE`), Telegram HTML with every value escaped: reason, question language,
  follow-up number, the question (cut at 3,000 characters; Telegram's limit is 4,096)
  and, when `DJANGO_SITE_URL` is set, a link that searches the admin for the follow-up
  number. Never the asker, and never an integer key.
- **Log**: `TelegramMessage` records every attempt: referral, kind, chat, Telegram's
  `message_id` (required when sent, by a named constraint), status, text and error. A
  failure is logged and saved, never raised. `services.resend` sends a failed notice
  again as a new row; the admin offers it as "Send selected failed messages again".
- **Chat IDs**: the `telegram_chats` command lists the chats found in `getUpdates`, to
  fill `Center.telegram_chat_id`; it never prints the token.

## Consequences

- The notice is sent in the asker's request, after the commit: it adds one HTTPS call
  (at most 5 seconds when Telegram is slow) to an answer that takes 20 to 45 seconds. A
  task queue would remove it, at the cost of a broker and a worker process.
- A failed notice is not retried automatically; staff resend it from the admin.
- `getUpdates` stops working once a webhook is set (step 3); chat IDs are then found
  from the webhook's updates.
- Translation of the question into the center's languages is the next step, through a
  translation crew in `agents`.
