---
id: data-model
title: Data model
sidebar_position: 2
description: Entity-relationship diagram, referential actions and database constraints of the core app.
---

# Data model

Field-level details: [Models reference](../reference/models.md).

## Entity-relationship diagram

```mermaid
erDiagram
    USER ||--o{ MEMBERSHIP : "has"
    CENTER ||--o{ MEMBERSHIP : "has"

    USER {
        bigint id PK
        uuid uuid UK "public identifier"
        varchar email UK "unique, also lower(email)"
        varchar full_name
        varchar preferred_lang "ar | en | fr"
        varchar avatar
        bigint telegram_chat_id UK "nullable"
        bool is_active
        bool is_staff
        bool is_superuser
        bool is_verified
        timestamptz created_at
        timestamptz updated_at
    }
    CENTER {
        bigint id PK
        varchar name UK
        varchar slug UK
        varchar country "ISO 3166-1 alpha-2"
        varchar logo
        text description
        varchar contact_email
        varchar website
        bigint telegram_chat_id "nullable, Telegram group"
        varchar_array languages
        bool is_default "at most one true"
        bool is_active
        timestamptz created_at
        timestamptz updated_at
    }
    MEMBERSHIP {
        bigint id PK
        uuid uuid UK "public identifier"
        bigint center_id FK
        bigint user_id FK
        varchar role "specialist | center_admin"
        bool is_active
        timestamptz left_at "null exactly when active"
        timestamptz created_at
        timestamptz updated_at
    }
```

`User` also has Django's `groups` and `user_permissions` many-to-many tables
(`PermissionsMixin`), omitted above.

## Referential actions

| From | To | `on_delete` | Why |
| --- | --- | --- | --- |
| `Membership.user` | `User` | `CASCADE` | A membership has no meaning without its user. Users are deactivated, not deleted, in normal operation. |
| `Membership.center` (via `CenterLinkedModel`) | `Center` | `CASCADE` | Every center-owned row belongs to the center; deleting a center removes its data. Centers are deactivated in normal operation. |
| `created_by` (via `CreatedByMixin`) | `User` | `SET_NULL` | Content must survive the deletion of its author. Not yet used by a concrete model. |

## Database constraints

Constraints are enforced by PostgreSQL, so they also hold for bulk updates, raw SQL and
concurrent requests. Each one also has a translated `violation_error_message`, reported
by `full_clean()`.

| Table | Constraint | Kind | Rule |
| --- | --- | --- | --- |
| `core_user` | `email` unique | unique | Exact email unique. |
| `core_user` | `unique_user_email_ci` | unique expression | `LOWER(email)` unique: emails differing only in case are the same account. |
| `core_user` | `uuid` unique | unique | Public identifier. |
| `core_user` | `telegram_chat_id` unique | unique | One account per Telegram chat; several NULLs allowed. |
| `core_center` | `name`, `slug` unique | unique | |
| `core_center` | `only_one_default_center` | partial unique | `UNIQUE (is_default) WHERE is_default`. |
| `core_membership` | `uuid` unique | unique | |
| `core_membership` | `unique_active_membership` | partial unique | `UNIQUE (user_id, center_id) WHERE is_active`. |
| `core_membership` | `membership_active_matches_left_at` | check | Active with no `left_at`, or inactive with `left_at`. |

## Rules outside the database

"A center keeps at least one active center admin" involves several rows and is enforced
by `core.services.memberships` under row locks, not by a constraint.

## Extensions

`vector` (pgvector) is enabled by the first operation of `core/migrations/0001_initial.py`
([ADR 0003](decisions/0003-pgvector-in-initial-migration.md)). No table uses it yet.
