---
id: 0004-single-default-center
title: "ADR 0004: A single default center"
sidebar_position: 4
description: Why at most one center is the default, enforced by a partial unique constraint and moved by make_default.
---

# ADR 0004: A single default center

## Status

Accepted, 2026-10-04.

## Context

Questions the AI must not answer are referred to a center of specialists. When no
specific center is chosen, one center must receive them. Two defaults would make routing
ambiguous; none would leave questions unrouted.

## Decision

- `Center.is_default`, with the partial unique constraint `only_one_default_center`
  (`UNIQUE (is_default) WHERE is_default`). PostgreSQL guarantees at most one default
  under any concurrency.
- `Center.save()` validates the constraint before writing when `is_default` is set, so
  a second default raises `ValidationError` with the constraint's translated message
  instead of a raw `IntegrityError`.
- `Center.make_default()` moves the flag in one transaction: it locks the current
  default and the target row (`SELECT ... FOR UPDATE`), clears the old flag, then sets
  the new one.

## Consequences

- The database allows zero defaults. Routing code must handle "no default center",
  for example by refusing to refer until one is configured.
- `save()` performs one extra query when saving a default center.
- Bulk updates bypass `save()`; they still hit the database constraint and fail with
  `IntegrityError`.
- Nothing prevents an inactive center from being the default; routing must check
  `is_active` or a later rule must forbid it.
