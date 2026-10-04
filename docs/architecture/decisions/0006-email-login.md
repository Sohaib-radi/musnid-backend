---
id: 0006-email-login
title: "ADR 0006: Email as the login identifier"
sidebar_position: 6
description: Why users log in with their email, matched case-insensitively and unique regardless of case.
---

# ADR 0006: Email as the login identifier

## Status

Accepted, 2026-10-04.

## Context

Specialists and administrators are invited by email and recover access by email. A
separate username adds something to remember and to keep unique. Email addresses are
treated as case-insensitive by users, and in practice by mail providers, although the
standard allows a case-sensitive local part.

## Decision

- `USERNAME_FIELD = 'email'`; there is no username.
- Login is case-insensitive: `UserManager.get_by_natural_key()` uses `email__iexact`.
  Django's `ModelBackend` calls it, so `Amina@Example.com` and `amina@example.com` log
  in to the same account.
- Uniqueness is case-insensitive: besides `unique=True`, the expression constraint
  `unique_user_email_ci` makes `LOWER(email)` unique, so two accounts can never differ
  only by case. Without it, the case-insensitive lookup could match two rows.
- The address is stored as entered, with only the domain lower-cased
  (`normalize_email`).

## Consequences

- Lookups by email elsewhere (for example `add_member`) must also use `iexact`.
- The `email` column has two unique indexes (exact and lower-cased). The exact one is
  redundant for correctness but keeps Django's per-field unique validation.
- Changing a user's email must keep it unique case-insensitively; the constraint
  enforces it.
