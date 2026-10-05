---
id: 0020-answer-revisions
title: "ADR 0020: Specialists revise answers; the asker sees the latest revision"
sidebar_position: 20
description: Answer revisions written by center members or staff, shown to the asker under the center's name, with the AI answer kept for audit.
---

# ADR 0020: Specialists revise answers; the asker sees the latest revision

## Status

Accepted, 2026-10-05.

## Context

The AI answers with verified quotes ([ADR 0016](0016-question-answering-flow.md)), but a
specialist may find an error, want to clarify an answer, or answer a question the AI
referred or abstained on. The asker must then see the specialist's text, from any device
when logged in ([ADR 0019](0019-link-questions-to-logged-in-askers.md)). The AI's
`Interaction` is the audit record of one answer and is used for evaluation, so it must
not change. The same rules must hold in the admin now, and later in the center dashboard
API and the Telegram bot.

## Decision

- **`AnswerRevision`** (`qa`): `question`, `author` (`SET_NULL`), `text`, `reason`
  (`correction`, `clarification`, `specialist_answer`), and an internal `note`. Rows are
  never edited: each change adds one, so the history keeps who changed what, when and why.
- **One entry point**: `qa.services.revise(question, author, text, reason, note)`. It
  checks the rules, locks the question row so concurrent revisions are ordered, and
  raises `ValidationError` with a code (`revision_not_allowed`,
  `revision_text_required`, `revision_text_too_long` (10,000 characters),
  `revision_reason_invalid`).
- **Who may revise** (`can_revise`): active staff with `qa.add_answerrevision`
  (superusers included), and active members (specialist or center admin) of the
  question's center while that center is operational.
- **What the asker sees**: the latest revision's text replaces the AI answer; sentences
  and notes are empty, since they belong to the AI answer. The payload adds
  `answered_by` (`ai` or `center`) and `review` (`center` name and `revised_at`). The
  author's name and the internal note are never returned: the center is responsible for
  the answer.
- **AI answer kept**: the `Interaction` is never modified; staff see it in the admin
  next to the revision history.
- **Admin**: a "Revise the answer" page, prefilled with the current answer (the AI text
  without `[Q<n>]` markers, or the latest revision), saves through `revise`; the question
  page lists revisions read-only; the list shows "Answered by" (AI or Center).
- **Queries**: `QuestionQuerySet.with_answers()` loads interactions, centers and
  revisions; a page of history takes four queries whatever its size.

## Consequences

- One rule set for every channel: the dashboard (step 4) and Telegram (step 5) call
  `revise` instead of saving revisions themselves.
- Revisions are plain text: a specialist's answer carries no verified quotes or
  sources. Linking a revision to sources is possible later.
- There is no review queue or assignment yet; any allowed user can revise any question
  of their center. Queues and assignment come with the dashboard endpoints.
- Migration `qa.0004_answer_revision` creates one table: no data change.
