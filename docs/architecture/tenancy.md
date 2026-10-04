---
id: tenancy
title: Tenancy
sidebar_position: 3
description: How data is scoped to centers through for_center and how memberships give users access to centers.
---

# Tenancy

The platform hosts several centers of specialists. Data that belongs to a center must
only be shown to, and changed by, that center's members. This page describes the
mechanisms; the decision is recorded in
[ADR 0005](decisions/0005-explicit-center-scoping.md).

## Center-owned data

A model owned by a center subclasses `CenterLinkedModel`. It then has:

- a non-nullable `center` foreign key (`CASCADE`);
- a default manager built from `CenterQuerySet`, which offers `for_center(center)`.

```python
from core.models import Membership

Membership.objects.for_center(center).active().center_admins()
Membership.objects.for_center(center.pk)   # a primary key works too
```

## Explicit scoping

The default manager is **not** scoped: `Model.objects.all()` returns rows of every
center. Code that acts on behalf of a center must call `for_center()` itself. There is
no thread-local "current center" and no manager that filters implicitly.

- Scoping is visible at the call site, so a review can see it.
- Cross-center code (platform staff tools, migrations, management commands, tests) uses
  the default manager without workarounds.
- `for_center(None)` and `for_center(unsaved_center)` raise `ValueError` instead of
  silently returning nothing, so a missing center is caught rather than hidden.

The risk is forgetting `for_center()`. Views and APIs, when they arrive, should obtain
querysets through a single helper or mixin that applies it.

## Membership: who belongs to which center

A user reaches a center only through a `Membership`
([ADR 0007](decisions/0007-membership-links-users-to-centers.md)):

| Role | Purpose |
| --- | --- |
| `specialist` | Answers questions referred to the center. |
| `center_admin` | Manages the center and its members. |

- A user can belong to several centers, with one active membership per center.
- Leaving deactivates the membership (`is_active=False`, `left_at` set); the row stays
  as history. Rejoining creates a new membership.
- Changes go through `core.services.memberships` (`add_member`, `change_role`,
  `offboard`), which keep at least one active center admin per center.

To list a user's centers: `user.memberships.active()`. To list a center's people:
`Membership.objects.for_center(center).active()`.

## The default center

One center can be marked default
([ADR 0004](decisions/0004-single-default-center.md)). It receives referred questions
when no other center is selected. `Center.make_default()` moves the flag atomically.
