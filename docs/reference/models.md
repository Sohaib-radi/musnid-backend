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
| `telegram_chat_id` | `BigIntegerField` | Label "Telegram Group ID". Nullable, unique when set (`unique_center_telegram_group`). Group where referred questions are sent, for example `-1001234567890`; set when a center admin connects the group through the bot, read-only in the API. |
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
| `unique_center_telegram_group` | `UNIQUE (telegram_chat_id) WHERE telegram_chat_id IS NOT NULL`: a Telegram group serves one center ([ADR 0023](../architecture/decisions/0023-answer-from-telegram.md)). Message: "This Telegram group is already connected to another center." |

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

## `ApiCredential` (`core/models/credentials.py`)

`BaseModel` + `CreatedByMixin`. Provider API keys, stored encrypted ([Provider API keys](api-keys.md)).

| Field | Type | Notes |
| --- | --- | --- |
| `provider` | `CharField(20)` | `ApiCredential.Provider`: `openai` ("OpenAI", not translated). |
| `name` | `CharField(100)` | E.g. "production key". |
| `encrypted_secret` | `TextField` | Fernet token. Not editable. |
| `fingerprint` | `CharField(64)` | SHA-256 of the key, unique. Not editable. |
| `prefix`, `last_four` | `CharField(3)`, `CharField(4)` | For the masked display. Not editable. |
| `is_active` | `BooleanField` | Default true. Not editable. |
| `revoked_at`, `revoked_by` | `DateTimeField`, `ForeignKey` (`SET_NULL`) | Set by revocation. Not editable. |

| Constraint | Definition |
| --- | --- |
| `one_active_credential_per_provider` | `UNIQUE (provider) WHERE is_active` |
| `credential_active_matches_revoked_at` | active with no `revoked_at`, or inactive with one |

Property `masked` (`sk-...abcd`); `__str__` and `__repr__` show only that.

## Services (`core/services/credentials.py`)

| Function | Behaviour | Error codes |
| --- | --- | --- |
| `validate_secret(provider, secret)` | OpenAI: starts with `sk-`, at least 20 characters, no whitespace; never added before (fingerprint). | `invalid_format`, `duplicate_secret` |
| `add_credential(provider, name, secret, created_by)` | Strips, validates, encrypts; revokes the provider's active key in the same transaction (`select_for_update`). | as above |
| `revoke(credential, revoked_by)` | Idempotent. | |
| `get_secret(provider)`, `get_openai_key()` | Active key, else `settings.OPENAI_API_KEY` (OpenAI), else `''`. | |

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

## `SourceDocument` (`knowledge/models.py`)

A vetted source book; its chunks are described in [RAG pipeline](../rag/02-pipeline.md).
Public links, used for the sources of answers ([ADR 0017](../architecture/decisions/0017-anonymous-ask-api.md)):

| Field or method | Meaning |
| --- | --- |
| `url` | Public page of the book (Bayyinat: `https://dawa.center/file/7937`). |
| `pdf_url` | Public PDF, the same file that was ingested (SHA-256 checked). |
| `page_url(language)` | `url` with `?lang=<language>` for `ar`, `en`, `fr`; `url` unchanged otherwise; empty without `url`. |
| `pdf_page_url(page)` | `pdf_url#page=<page + 1>`: printed page numbers equal the 0-based PDF index, viewers count from 1. Empty without `pdf_url`. |

## `Question`, `Interaction` and `Referral` (`qa/models.py`)

Every question and how it was answered ([ADR 0016](../architecture/decisions/0016-question-answering-flow.md)). Anonymous unless the asker was logged in ([ADR 0019](../architecture/decisions/0019-link-questions-to-logged-in-askers.md)).

| Model | Field | Meaning |
| --- | --- | --- |
| `Question` | `uuid` | Public identifier, unique; also the follow-up number of a referred question. |
| `Question` | `text`, `lang`, `session_id` | The question, its detected language, and the opaque session id from the frontend. |
| `Question` | `translations` | Machine translations of the text for specialists, `{"ar": "…"}`, filled when a notice needs one (`agents.translation`). |
| `Question` | `asker` | The user who asked while logged in; null for anonymous askers. `SET_NULL`: deleting the account keeps the question, anonymous. Never returned by the public API. |
| `AnswerRevision` | `question`, `author`, `text`, `lang`, `translated_text`, `reason`, `note` | A version of the answer written by a person ([ADR 0020](../architecture/decisions/0020-answer-revisions.md)); `reason` is `correction`, `clarification` or `specialist_answer`; `note` is internal. Never edited; created only by `qa.services.revise`. `Question.latest_revision()` returns the newest. `lang` is the language the author wrote in; when it differs from the question's, `revise` stores an AI translation in `translated_text` and the asker sees it (`shown_text`). |
| `HumanLabel` | `interaction`, `reviewer`, `verdict`, `reason`, `corrected_answer` | A reviewer's verdict on an AI answer ("AI verdict"): `approve` (Correct), `correct` (To correct, with the corrected answer), `reject` (Wrong, with a reason). One per reviewer and interaction (`one_label_per_reviewer`); saved only by `qa.services.label`, which needs the `revise` permission and never changes what the asker sees. |
| `Interaction` | `decision`, `level`, `answer_text`, `citations` | What was returned, the classifier's level, the shown text, the valid `[Q<n>]` numbers. |
| `Interaction` | `sentences` | Kept sentences: `text` (markers removed), `quote`, `number` (the evidence question containing the quote, found in code). Empty for fixed replies. |
| `Interaction` | `dropped` | Sentences removed by the checks: `text`, `quote`, `reason` (`quote` or `entailment`). |
| `Interaction` | `evidence` | The exact evidence text the writer received (Bayyinat passages with `[Q<n>]` markers); empty for fixed replies and for answers saved before 2026-10-06. Kept so an answer can be rebuilt as the model saw it (fine-tuning dataset). Never returned by the API. |
| `Interaction` | `retrieved`, `evidence_question_numbers`, `verifier_verdict`, `model_name`, `prompt_version`, `latency_ms`, `tokens_in`, `tokens_out`, `error` | The trace, for review; never returned by the API. |

`QuestionQuerySet` (the manager of `Question`, based on `CenterQuerySet`):

| Method | Returns |
| --- | --- |
| `for_session(session_id)` | That session's questions, newest first (index `question_session_recent`). |
| `with_answers()` | Joins the interaction, center and referral and prefetches the revisions, for the public payload. |
| `for_asker(user)` | That user's questions from every session, newest first (index `question_asker_recent`). |
| `asked_today()` | Questions created since 00:00 UTC, across all centers; counted for `ASK_DAILY_LIMIT`. |

### `Referral` (`qa/models.py`)

The ticket of a referred question ([ADR 0021](../architecture/decisions/0021-referral-tickets.md)).
A `CenterLinkedModel`; opened by `agents.services.ask` when the decision is `refer`, and
changed only through `qa.services`.

| Field | Meaning |
| --- | --- |
| `question` | One-to-one with the referred `Question` (`related_name="referral"`). |
| `center` | The center that should answer; the question's center when opened. |
| `reason` | `level_d` (personal ruling, classifier level D) or `no_evidence` (not covered by the sources). Set in code. |
| `status` | `open` (default), `in_progress`, `answered`, `closed` (closed without an answer). |
| `assigned_to` | The specialist handling it; `SET_NULL`. |
| `answered_at`, `closed_at` | Dates of the first answer and of closing. |
| `close_note` | Why it was closed without an answer; internal, never returned by the API. |

| Constraint or index | Rule |
| --- | --- |
| `referral_answered_has_date` | `status = answered` requires `answered_at`. |
| `referral_closed_has_date` | `status = closed` requires `closed_at`. |
| `referral_center_queue` | Index on `center`, `status`, `-created_at`, for a center's queue. |

`ReferralQuerySet` (based on `CenterQuerySet`): `pending()` (open or in progress),
`assigned_to(user)`. `Referral.is_pending` is the same test on one row.

`open_referral` sends `qa.signals.referral_opened` (argument `referral`) with
`send_robust` once the transaction commits; `telegram_bot` listens to it.

### Services (`qa/services.py`)

| Function | Rule |
| --- | --- |
| `can_revise(user, question)` | Active staff with `qa.add_answerrevision`, or an active member of the question's operational center. |
| `revise(question, author, text, reason, note="")` | Adds an `AnswerRevision`; marks the question's referral `answered` if it is not already. Codes: `revision_not_allowed`, `revision_text_required`, `revision_text_too_long`, `revision_reason_invalid`. |
| `open_referral(question, reason)` | Opens the referral, owned by the question's center. |
| `assign(referral, user, assignee)` | `user` must pass `can_revise`; `assignee` must be an active member of the center; status `in_progress`. Codes: `referral_not_allowed`, `referral_assignee_invalid`, `referral_not_pending`. |
| `close(referral, user, note)` | Status `closed` with the note. Codes: `referral_not_allowed`, `referral_note_required`, `referral_not_pending`. |

## `TelegramMessage` (`telegram_bot/models.py`)

One row per attempt to send a Telegram message ([ADR 0022](../architecture/decisions/0022-telegram-channel.md)).

| Field | Meaning |
| --- | --- |
| `referral` | The referral the message is about; `CASCADE`. |
| `kind` | `referral_notice` (the notice of a new referral). |
| `chat_id` | The Telegram chat it was sent to (`Center.telegram_chat_id` at the time). |
| `message_id` | Telegram's id of the sent message; null when it failed. Used later to match replies. |
| `status` | `sent` or `failed`. |
| `text`, `error` | The text sent (Telegram HTML) and Telegram's error description; never the token. |

| Constraint or index | Rule |
| --- | --- |
| `telegram_sent_has_message_id` | `status = sent` requires `message_id`. |
| `telegram_message_lookup` | Index on `chat_id`, `message_id`, to find the message a reply answers. |

## `TelegramLinkCode` (`telegram_bot/models.py`)

A one-time code linking a Telegram account to a user ([ADR 0023](../architecture/decisions/0023-answer-from-telegram.md)).

| Field | Meaning |
| --- | --- |
| `user` | The user the code links; `CASCADE`. |
| `code_hash` | SHA-256 of the code, unique; the code itself is never stored. |
| `center` | Set for a group connection code (`startgroup` link); empty for a personal link. |
| `expires_at`, `used_at` | Ten minutes after creation; set once used. `TelegramLinkCode.objects.usable()` returns codes neither used nor expired. |

`telegram_bot.linking`: `create_group_link(center, user, client=None)` (code
`telegram_not_center_admin`) and `connect_group(code, chat_id, telegram_id)` (codes
`telegram_link_invalid`, `telegram_group_taken`) connect a center's group;
`disconnect_center(center, user, client=None)` (code `telegram_not_center_admin`) clears the
group and makes the bot leave it; `disconnect_group(chat_id)` and `move_group(old, new)`
follow removal and supergroup upgrades. `create_link(user, client=None)` returns `(url, expires_at)`;
`link_account(code, telegram_id)` saves `User.telegram_chat_id` (codes
`telegram_link_invalid`, `telegram_already_linked`, `telegram_link_inactive_user`).
`telegram_bot.updates.handle_update(update, client=None)` links on `/start <code>` and saves
a linked user's reply to a referral notice through `qa.services.revise`.

Services (`telegram_bot/services.py`): `notify_referral(referral, client=None)` posts the
notice and logs it, returning `None` without calling Telegram when the bot has no token or
the center no group; `resend(message, client=None)` sends a failed notice again (codes
`telegram_not_failed`, `telegram_unavailable`); `referral_notice(referral)` builds the text.

