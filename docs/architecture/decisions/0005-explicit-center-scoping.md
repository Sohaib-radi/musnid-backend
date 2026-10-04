---
id: 0005-explicit-center-scoping
title: "ADR 0005: Explicit center scoping"
sidebar_position: 5
description: Why center-owned querysets are scoped with an explicit for_center() call instead of an implicit, scoped default manager.
---

# ADR 0005: Explicit center scoping

## Status

Accepted, 2026-10-04.

## Context

Several centers share one database. A center's members must only see that center's
data. Common approaches in Django:

1. **Implicit scoping**: the default manager filters by a "current center" stored in a
   thread-local or context variable, set by middleware.
2. **Separate schemas or databases** per center.
3. **Explicit scoping**: models carry a `center` foreign key and callers filter
   explicitly.

Implicit scoping hides the filter: a query looks unscoped but is not, and code without
a request (management commands, background tasks, tests) must fake a current center.
Separate schemas multiply migrations and complicate cross-center features such as the
default center and platform-wide administration.

## Decision

Explicit scoping. Center-owned models subclass `CenterLinkedModel`, whose default
manager is a `CenterQuerySet` with `for_center(center)`. The default manager is not
scoped. `for_center()` rejects `None` and unsaved centers with `ValueError`.

## Consequences

- Every query that serves a center must call `for_center()`. Forgetting it leaks data
  across centers; this is the main risk. Views and APIs should get querysets from one
  shared helper or mixin that applies it, and tests should cover cross-center access.
- Scoping is visible in code review.
- Cross-center work needs no special mechanism.
- See [Tenancy](../tenancy.md).
