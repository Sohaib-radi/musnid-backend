---
id: models
title: Models
sidebar_position: 1
description: Every model, field, method, queryset and constraint in the core app.
---

# Models

All models live in the `core.models` package, one module per concern, and are imported
from `core.models`. Diagrams and referential actions:
[Data model](../architecture/data-model.md).

## Abstract building blocks (`core/models/base.py`)

### `BaseModel`

Abstract base of every concrete model.

| Field | Type | Notes |
| --- | --- | --- |
| `created_at` | `DateTimeField` | `auto_now_add`, indexed. |
| `updated_at` | `DateTimeField` | `auto_now`. |

- `Meta.ordering = ['-created_at']` (newest first).
- A concrete model that declares `Meta` must subclass `BaseModel.Meta` to keep the
  ordering. Django resets `abstract` to false on the inherited `Meta`.
- `auto_now` only runs when the field is written. `save(update_fields=[...])` must list
  `'updated_at'`, and `QuerySet.update()` must set `updated_at=timezone.now()`.

### `CenterLinkedModel`

Abstract base for rows owned by one center.

| Field | Type | Notes |
| --- | --- | --- |
| `center` | `ForeignKey` to `core.Center` | `CASCADE`; `related_name='%(app_label)s_%(class)s_set'`, `related_query_name='%(app_label)s_%(class)s'`. |

- Default manager: `CenterQuerySet.as_manager()`. It is **not** scoped; see
  [Tenancy](../architecture/tenancy.md).

### `CenterQuerySet`

| Method | Returns |
| --- | --- |
| `for_center(center)` | Rows of `center` (a saved `Center` or its primary key). Raises `ValueError` for `None` or an unsaved center. |

### `CreatedByMixin`

| Field | Type | Notes |
| --- | --- | --- |
| `created_by` | `ForeignKey` to the user model | `SET_NULL`, nullable, `related_name='+'` (no reverse accessor). |

## `Language` (`core/models/choices.py`)

`TextChoices`: `ARABIC = 'ar'`, `ENGLISH = 'en'`, `FRENCH = 'fr'`. Must equal
`settings.LANGUAGES` (enforced by `test_choices.py`).

## `User` (`core/models/user.py`)

`BaseModel` + `AbstractBaseUser` + `PermissionsMixin`. `AUTH_USER_MODEL = 'core.User'`.
`USERNAME_FIELD = 'email'`, `EMAIL_FIELD = 'email'`, `REQUIRED_FIELDS = ['full_name']`.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | `BigAutoField` | Internal only; never exposed. |
| `uuid` | `UUIDField` | Public identifier. Unique, `uuid4` default, not editable. |
| `email` | `EmailField` | Unique; also unique case-insensitively (constraint below). |
| `full_name` | `CharField(150)` | Required. |
| `preferred_lang` | `CharField(2)` | `Language`, default `en`. |
| `avatar` | `ImageField` | Optional; uploaded to `media/users/avatars/`. |
| `telegram_chat_id` | `BigIntegerField` | Unique, nullable. Set when the user links Telegram. |
| `is_active` | `BooleanField` | Default true. Inactive users cannot log in. |
| `is_staff` | `BooleanField` | Default false. Admin site access. |
| `is_verified` | `BooleanField` | Default false. Email confirmed. |
| `password`, `last_login` | | From `AbstractBaseUser`. |
| `is_superuser`, `groups`, `user_permissions` | | From `PermissionsMixin`. |
| `created_at`, `updated_at` | | From `BaseModel`. |

| Constraint | Definition |
| --- | --- |
| `unique_user_email_ci` | `UNIQUE (LOWER(email))`. Message: "A user with this email address already exists." |

Methods: `__str__` returns the email; `get_full_name()` and `get_short_name()` return
`full_name`; `clean()` normalises the email's domain to lower case.

### `UserManager`

| Method | Behaviour |
| --- | --- |
| `create_user(email, full_name, password=None, **extra)` | `is_staff` and `is_superuser` false. Domain of the email lower-cased. `password=None` stores an unusable password. Empty email raises `ValueError`. |
| `create_superuser(email, full_name, password=None, **extra)` | `is_staff` and `is_superuser` true; passing either as false raises `ValueError`. |
| `get_by_natural_key(email)` | Case-insensitive lookup (`email__iexact`). Used by `ModelBackend`, so login ignores case. |

## `Center` (`core/models/center.py`)

`BaseModel`.

| Field | Type | Notes |
| --- | --- | --- |
| `name` | `CharField(200)` | Unique. |
| `slug` | `SlugField(200)` | Unique. |
| `country` | `CountryField` | Optional, ISO 3166-1 alpha-2 code (django-countries). |
| `logo` | `ImageField` | Optional; uploaded to `media/centers/logos/`. |
| `description` | `TextField` | Optional. |
| `contact_email` | `EmailField` | Optional. |
| `website` | `URLField` | Optional. |
| `telegram_chat_id` | `BigIntegerField` | Label "Telegram Group ID". Nullable. Group where referred questions are sent, for example `-1001234567890`. |
| `languages` | `ArrayField` of `CharField(2)` with `Language` choices | Languages served. Default empty list. |
| `is_default` | `BooleanField` | Default false. At most one center, approved only (constraints below). |
| `is_active` | `BooleanField` | Default true. Unchecked suspends an approved center. |
| `status` | `CharField(10)` | `Center.Status`: `pending`, `approved` (default), `rejected`. Changed only by `core.services.centers`. |
| `reviewed_at` | `DateTimeField` | Nullable. Set by the review. |
| `reviewed_by` | `ForeignKey` to the user model | `SET_NULL`, nullable, no reverse accessor. |
| `rejection_reason` | `TextField` | Optional. Shown to the applicant. |

| Constraint | Definition |
| --- | --- |
| `only_one_default_center` | `UNIQUE (is_default) WHERE is_default`. Message: "Only one center can be the default center." |
| `default_center_must_be_approved` | `CHECK (NOT is_default OR status = 'approved')`. Message: "Only an approved center can be the default center." |

`Center.objects` is a `CenterStatusQuerySet`: `operational()` (approved and active),
`pending()`, `with_active_member(user)` (centers where `user` has an active membership).
Property `is_operational`: approved and active.

| Method | Behaviour |
| --- | --- |
| `save()` | When `is_default` is true, runs `validate_constraints()` first, so a second default raises `ValidationError` with the constraint's translated message. The database constraint remains the final guard. |
| `make_default()` | Refuses a non-approved center (`ValidationError`, code `center_not_approved`). In one transaction, locks the current default and this row (`SELECT ... FOR UPDATE`), unsets the previous default (with `updated_at`), then sets this one. Idempotent. |

## `Membership` (`core/models/membership.py`)

`BaseModel` + `CenterLinkedModel`. Reverse accessors: `user.memberships`,
`center.core_membership_set`.

| Field | Type | Notes |
| --- | --- | --- |
| `uuid` | `UUIDField` | Public identifier, unique. |
| `center` | `ForeignKey` to `Center` | From `CenterLinkedModel`, `CASCADE`. |
| `user` | `ForeignKey` to `User` | `CASCADE`, `related_name='memberships'`. |
| `role` | `CharField(20)` | `Membership.Role`: `specialist`, `center_admin`. |
| `is_active` | `BooleanField` | Default true. |
| `left_at` | `DateTimeField` | Nullable. When the user left. |

| Constraint | Definition |
| --- | --- |
| `unique_active_membership` | `UNIQUE (user, center) WHERE is_active`. One active membership per user and center; former memberships are kept. |
| `membership_active_matches_left_at` | `CHECK ((is_active AND left_at IS NULL) OR (NOT is_active AND left_at IS NOT NULL))`. |

### `MembershipQuerySet`

Extends `CenterQuerySet`. Each method applies one filter; they chain.

| Method | Filter |
| --- | --- |
| `for_center(center)` | Inherited. |
| `active()` | `is_active=True` |
| `center_admins()` | `role='center_admin'` (active or not) |
| `specialists()` | `role='specialist'` (active or not) |

## Services (`core/services/centers.py`)

| Function | Behaviour | Error codes |
| --- | --- | --- |
| `register_center(applicant, **fields)` | Creates a `pending` center (slug from the name when omitted, unique) and makes `applicant` its center admin, in one transaction. Ignores `status`, review fields and `is_default` from the caller. | those of `add_member` |
| `approve(center, reviewer)` | Pending to approved; records reviewer and date. | `center_not_pending` |
| `reject(center, reviewer, reason)` | Pending to rejected with the (trimmed) reason. | `rejection_reason_required`, `center_not_pending` |
| `unique_slug(name)` | A free slug; Arabic names fall back to `center`, then `center-2`, … | |

Reviews lock the center row (`SELECT ... FOR UPDATE`) so two reviewers cannot both
review it.

## Services (`core/services/memberships.py`)

Rules that involve several memberships. Each failure raises `ValidationError` with the
code shown.

| Function | Behaviour | Error codes |
| --- | --- | --- |
| `add_member(center, email, role)` | Finds the user by email (case-insensitive, trimmed) and creates an active membership. | `invalid_role`, `user_not_found`, `user_inactive`, `already_member` |
| `change_role(membership, role)` | Changes the role. Same role is a no-op. | `invalid_role`, `membership_inactive`, `last_center_admin` |
| `offboard(membership)` | Sets `is_active=False` and `left_at=now`. Never deletes. | `membership_inactive`, `last_center_admin` |
| `validate_add_member(center, user, role)` | Runs `add_member`'s checks without saving; used by the admin form. | `invalid_role`, `user_inactive`, `already_member` |
| `validate_change_role(membership, role)` | Runs `change_role`'s checks without saving. Reads the stored state, so an instance already modified in memory (a bound form's) is fine. | `invalid_role`, `membership_inactive`, `last_center_admin` |

`last_center_admin`: a center that has an active center admin must keep at least one.
A new center has none, and `add_member` accepts any role, so the first admin can be added.
`change_role` and `offboard` lock the center's active admin memberships, in primary key
order, before checking, so concurrent calls cannot remove the last admin together or
deadlock. The `validate_*` functions read without locks; the mutating functions check
again under the locks, which is what guarantees the rules.
