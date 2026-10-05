---
id: telegram-bot
title: Telegram bot
sidebar_position: 5
description: How specialists receive and answer referred questions in Telegram, with a real example; what works today and what is planned.
---

# Telegram bot

Askers ask on the website. Specialists answer in Telegram. The bot carries the question
to the specialists and the answer back to the asker
([ADR 0022](../architecture/decisions/0022-telegram-channel.md),
[ADR 0023](../architecture/decisions/0023-answer-from-telegram.md)).

## 1. Setup, once per center

| Step | Who | What |
| --- | --- | --- |
| Group | Center admin | Creates one Telegram group, then clicks **Connect to Telegram** in the center dashboard and picks that group. The page shows a spinner, then "Connected"; the bot confirms in the group. The admin's own account is linked at the same time. |
| Specialists | Each specialist | Opens their personal link (admin → Telegram messages → "Link a Telegram account"; later a QR code in the center dashboard) and presses **Start**. The bot answers "Your Telegram account is now linked to Amina." Then joins the center's group. |

Many specialists can be linked; each link works once, for 10 minutes. **Disconnect** in
the dashboard removes the group: the bot says goodbye and leaves it.

## 2. A real interaction

**Asker, on the website** (French):

> Puis-je combiner les prières en voyage si je reste une semaine dans une autre ville ?

The AI sees a personal ruling (level D) and does not answer. The asker reads: "Votre
question nécessite un spécialiste. Elle a été transmise à un centre de spécialistes, qui
vous répondra." A ticket opens: **Open**.

**Center's group, seconds later:**

```text
سؤال جديد مُحال إلى مركزكم
السبب: فتوى شخصية (المستوى D)
اللغة: الفرنسية
رقم المتابعة: 3f2c9a1e-…

┃ Puis-je combiner les prières en voyage si je reste une semaine dans une autre ville ?
```

**Amina, a linked specialist, replies to that message:**

> Oui, selon l'avis majoritaire, tant que vous n'avez pas l'intention de rester plus de quatre jours…

**Bot, in the group:** "La réponse a été envoyée à l'auteur de la question."

**Asker, on the website:** sees Amina's answer, signed with the center's name (never
hers). The ticket is **Answered**.

## 3. What the bot refuses

| Case | Bot replies |
| --- | --- |
| A group already connected to another center | "This Telegram group is already connected to another center." |
| A group member who never linked replies | "Link your Telegram account first: ask your center for your link." |
| A linked user from another center replies | "You cannot revise answers of this center." |
| A photo or voice note instead of text | "Send the answer as text." |
| An expired or used link | "This link is invalid or expired. Ask for a new one." |

Messages that are not replies to the bot's notices are ignored.

## 4. Running it

| Where | How the bot receives messages |
| --- | --- |
| Local | `manage.py telegram_poll` (Ctrl+C to stop). |
| Production | Webhook `https://api.musnid.online/telegram/webhook/`, registered once with `manage.py telegram_webhook --set`. |

## 5. Planned

| Step | Real example |
| --- | --- |
| Translation | Amina answers in Arabic; the French asker reads it in French with "Translated from Arabic by AI"; the original is kept. |
| Private first, group after 1 minute | The question goes privately to the linked specialists; if nobody takes it within a minute, it goes to the group. |
| "Ask a specialist" | A button on the website for any question, not only those the AI refers. |
| Several centers | A question goes to a center serving the asker's language, or to the center the asker picks. Today: the default center. |

## Rules

- The group never sees who asked.
- The answer is published under the center's name; the specialist is kept in the history.
- The bot token and the webhook secret never appear in messages, logs or errors.
