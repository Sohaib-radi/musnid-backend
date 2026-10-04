---
id: 0007-membership-links-users-to-centers
title: "ADR 0007: Membership links users to centers"
sidebar_position: 7
description: Why users belong to centers through a Membership model with roles, deactivated rather than deleted.
---

# ADR 0007: Membership links users to centers

## Status

Accepted, 2026-10-04.

## Context

A specialist may serve several centers, and a center has several specialists and
administrators. Roles are per center: someone can administer one center and be a
specialist in another. Who belonged to which center, and when, matters for
accountability of past answers.

A `center` foreign key on `User`, or Django groups, cannot express per-center roles or
history.

## Decision

- A `Membership` model (`CenterLinkedModel`) links a user to a center with a role:
  `specialist` or `center_admin`.
- `unique_active_membership`: at most one active membership per user and center.
- Leaving deactivates the membership and records `left_at`; it is never deleted.
  `membership_active_matches_left_at` keeps the two fields consistent. Rejoining creates
  a new membership, so the history shows each period.
- Rules spanning several memberships live in `core.services.memberships`
  (`add_member`, `change_role`, `offboard`). The main one: a center that has an active
  center admin must keep at least one. Violations raise `ValidationError` with a code.
- Memberships have a public `uuid`, like users.

## Consequences

- Permission checks ask "does this user have an active membership of this center with
  this role", via `Membership.objects.for_center(c).active()`.
- Code must change memberships through the services, not with direct `save()` calls, to
  keep the admin rule. The database does not enforce that rule.
- A new center starts with no admin; the first `add_member(..., center_admin)`, or
  promoting a specialist with `change_role`, creates one.
