---
id: 0021-referral-tickets
title: "ADR 0021: A referred question opens a ticket for its center"
sidebar_position: 21
description: Referral tickets with a status, a reason and an assignee, opened by the ask service and changed only through qa.services.
---

# ADR 0021: A referred question opens a ticket for its center

## Status

Accepted, 2026-10-05.

## Context

Routing the questions the AI must not answer to centers of specialists is the core of
the project. Until now a `refer` decision ([ADR 0016](0016-question-answering-flow.md))
saved the question under the default center and gave the asker a follow-up number
([ADR 0017](0017-anonymous-ask-api.md)), but nothing recorded that the question was
waiting for a specialist: no status, no assignee, no queue. A specialist could answer
through a revision ([ADR 0020](0020-answer-revisions.md)), yet nobody could list what
was still unanswered, and the asker could not tell whether anyone was working on it.
The admin needs this queue now; the Telegram bot and the center dashboard need it next.

## Decision

- **`Referral`** (`qa`, a `CenterLinkedModel`): one per referred question
  (`question` one-to-one), with `reason`, `status`, `assigned_to` (`SET_NULL`),
  `answered_at`, `closed_at` and an internal `close_note`.
  - `reason` is set in code from the flow's result: `level_d` (a personal ruling, the
    classifier's level D) or `no_evidence` (the answer was not supported by the sources).
  - `status`: `open` → `in_progress` (assigned) → `answered`, or `closed` without an
    answer. Two named check constraints require `answered_at` for `answered` and
    `closed_at` for `closed`.
- **A separate model, not a status on `Question`**: the question stays the asker's
  record, `Interaction` the audit of the AI answer, and the ticket holds the center's
  workflow. A ticket can later move to another center without touching the question.
- **Opened by `ask()`** when the decision is `refer`, in the same transaction as the
  question and its interaction, owned by the question's center (the default center,
  [ADR 0004](0004-single-default-center.md)).
- **Changed only through `qa.services`**, with `ValidationError` codes:
  - `assign(referral, user, assignee)`: `user` must pass `can_revise`; `assignee` must
    be an active member of the referral's center; status becomes `in_progress`.
  - `close(referral, user, note)`: a note is required; status becomes `closed`.
  - Both lock the referral row and refuse a ticket already answered or closed
    (`referral_not_pending`). Other codes: `referral_not_allowed`,
    `referral_assignee_invalid`, `referral_note_required`.
  - `revise()` marks the question's referral `answered` (with `answered_at`) on the
    first revision, whatever its reason, since the asker now sees a specialist's text.
    A closed referral answered later becomes answered.
- **Asker**: the question payload adds `referral_status` (`open`, `in_progress`,
  `answered`, `closed`, or `null` when not referred). The assignee and the closing note
  are never returned.
- **Admin**: a read-only Referrals list with a sidebar badge of pending tickets, and two
  actions, "Assign selected referrals to me" and "Close selected referrals without an
  answer" (with an intermediate page for the note). Answers are still written on the
  question's "Revise the answer" page.
- **Existing data**: migration `qa.0005_referral` opens a ticket for every question
  already referred, dated like the question, `answered` at the newest revision when one
  exists, otherwise `open`.

## Consequences

- Every channel shares one queue and one rule set: the Telegram bot will notify on
  `open_referral` and answer through `revise`; the dashboard will list
  `Referral.objects.for_center(center).pending()`.
- Abstained questions open no ticket yet; an "ask a specialist" request from the asker
  is a later step and would add a reason.
- Every referral goes to the default center; choosing a center (by language or
  specialty) is a later step.
- Assignment is advisory: any member allowed to revise can still answer a ticket
  assigned to someone else.
