---
id: 0002-custom-user-model
title: "ADR 0002: Custom user model"
sidebar_position: 2
description: Why the project defines core.User from the start instead of using Django's built-in user.
---

# ADR 0002: Custom user model

## Status

Accepted, 2026-10-04.

## Context

The platform's users are specialists, center administrators and staff. They need fields
Django's `auth.User` does not have: a public UUID, a preferred language, an avatar, a
Telegram chat ID, an email-verified flag. They log in by email and have no username.

Django's documentation recommends a custom user model for every new project, because
`AUTH_USER_MODEL` cannot be changed easily once migrations reference the user table.
This was confirmed in practice: switching after the first step's `auth` and `admin`
migrations made `migrate` fail with `InconsistentMigrationHistory`, and the (empty)
local database had to be recreated.

## Decision

Define `core.User` on `AbstractBaseUser` and `PermissionsMixin` (plus `BaseModel` for
timestamps), with `UserManager`, and set `AUTH_USER_MODEL = 'core.User'` before any
production data exists.

`AbstractBaseUser` rather than `AbstractUser`: `AbstractUser` brings `username`,
`first_name` and `last_name`, which this project does not want. A single `full_name`
fits Arabic and French naming better than a first/last split.

## Consequences

- All code refers to the user model through `settings.AUTH_USER_MODEL` (in foreign keys)
  or `get_user_model()`, never `django.contrib.auth.models.User`.
- Profile data lives on the user row; there is no separate profile model.
- The admin will need a custom `UserAdmin` (forms for email and `full_name`) when the
  admin is added.
- Any developer database created before this change must be recreated
  ([Migrations](../../development/migrations.md#resetting-the-local-database)).
