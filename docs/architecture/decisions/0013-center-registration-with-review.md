---
id: 0013-center-registration-with-review
title: "ADR 0013: Center registration with review"
sidebar_position: 13
description: Why centers can register themselves but start pending, and how staff approve or reject them.
---

# ADR 0013: Center registration with review

## Status

Accepted, 2026-10-04.

## Context

Centers of specialists answer the questions the AI must not answer, so who runs a
center matters. Centers should be able to apply online, but nothing they do should take
effect before staff check them.

## Decision

- `Center.status`: `pending`, `approved` or `rejected`, plus `reviewed_at`,
  `reviewed_by` (`SET_NULL`) and `rejection_reason` (shown to the applicant).
- Centers created in the admin default to `approved`; migration `0002_center_review`
  makes existing centers approved. `POST auth/register/center/` creates the account and
  a `pending` center through `core.services.centers.register_center`, and makes the
  applicant its center admin.
- `is_active` keeps its meaning: it suspends an approved center. A center is
  **operational** when approved and active (`Center.objects.operational()`).
- Review only through `core.services.centers`: `approve(center, reviewer)` and
  `reject(center, reviewer, reason)`, only for pending centers (`center_not_pending`), a
  reason being required (`rejection_reason_required`). The status is never edited
  directly; the admin shows it read-only.
- Check constraint `default_center_must_be_approved`; `make_default()` refuses a
  non-approved center (`center_not_approved`).
- The API exposes the outcome to applicants: members can read their center in any
  state, and `state` (`pending_review`, `rejected`, `suspended`, `operational`) drives the
  frontend. Center-admin endpoints require an operational center
  (`center_not_operational`).
- The admin offers bulk approve/reject, per-row and per-page Approve/Reject buttons with
  confirmation dialogs on pending centers only, and a sidebar badge counting pending
  centers.

## Consequences

- A rejected center stays rejected: re-applying means a new registration (a new slug).
- Reviewers are not notified of new applications yet; the sidebar badge is the signal.
- Applicants are not notified of decisions yet; they see them on their next login.
