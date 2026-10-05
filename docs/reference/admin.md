---
id: admin
title: Admin
sidebar_position: 2
description: Every admin of the project, its list, filters, actions, inlines and forms, and the Unfold sidebar.
---

# Admin

The admin is Django's, styled with [Unfold](https://unfoldadmin.com/) 0.108.0
([ADR 0008](../architecture/decisions/0008-unfold-admin-theme.md)). Code:
`core/admin.py` (admins), `core/forms.py` (forms), `config/unfold.py` (theme and
sidebar). URL: `/admin/`.

## Rules

- Every admin inherits `unfold.admin.ModelAdmin`; every inline uses Unfold's
  `TabularInline` or `StackedInline`. `core/tests/test_admin.py` fails otherwise.
  Third-party models are re-registered with an Unfold admin (currently `Group`).
- Memberships change only through `core.services.memberships`
  ([ADR 0007](../architecture/decisions/0007-membership-links-users-to-centers.md)): the
  membership admin saves through the services, its form runs the same checks first, and
  memberships cannot be deleted.
- Every label, action and message is translated into Arabic and French
  ([ADR 0009](../architecture/decisions/0009-translations-in-every-change.md)).
- The admin app heading and breadcrumb read "Musnid" (`CoreConfig.verbose_name`), a
  brand name and therefore not translated.

## Sidebar

Defined in `UNFOLD["SIDEBAR"]` (`config/unfold.py`). Search is enabled; the default
"all applications" list is hidden.

| Group | Item | Icon (Material Symbols) | Link | Shown when the user has |
| --- | --- | --- | --- | --- |
| Centers | Centers | `apartment` | `admin:core_center_changelist` | `core.view_center` |
| Centers | Memberships | `badge` | `admin:core_membership_changelist` | `core.view_membership` |
| Questions and answers | Questions | `forum` | `admin:qa_question_changelist` | `qa.view_question` |
| Accounts | Users | `person` | `admin:core_user_changelist` | `core.view_user` |
| Accounts | Groups | `group` | `admin:auth_group_changelist` | `auth.view_group` |
| Knowledge base | Source documents | `menu_book` | `admin:knowledge_sourcedocument_changelist` | `knowledge.view_sourcedocument` |
| Knowledge base | Source chunks | `segment` | `admin:knowledge_sourcechunk_changelist` | `knowledge.view_sourcechunk` |
| Configuration | API Keys | `vpn_key` | `admin:core_apicredential_changelist` | `core.view_apicredential` |
| Configuration | AI settings | `smart_toy` | `admin:core_aisettings_changelist` | `core.view_aisettings` |
| Security | Outstanding tokens | `key` | `admin:token_blacklist_outstandingtoken_changelist` | `token_blacklist.view_outstandingtoken` |
| Security | Blacklisted tokens | `block` | `admin:token_blacklist_blacklistedtoken_changelist` | `token_blacklist.view_blacklistedtoken` |

The Centers item shows a badge with the number of pending centers
(`core.admin.pending_centers_badge`), empty when there are none.

The user menu at the bottom of the sidebar has a language switcher
(`UNFOLD["SHOW_LANGUAGES"]`) for Arabic, English and French. It posts to Django's
`set_language` view (`/i18n/setlang/`), which stores the choice in the `django_language`
cookie. Arabic renders right to left.

## Users (`UserAdmin`)

Based on Django's `UserAdmin`, adapted to `core.User` (email login, no username).

| Aspect | Definition |
| --- | --- |
| Forms | `UserChangeForm`, `UserCreationForm`, `AdminPasswordChangeForm` in `core/forms.py`: Unfold's styled auth forms rebound to `core.User`. |
| List columns | email, full name, preferred language, active, staff, email verified, created at |
| Filters | active, staff, superuser, email verified, preferred language, groups |
| Search | email, full name |
| Ordering | newest first |
| Fieldsets | Profile (email, full name, preferred language, avatar, Telegram chat ID, public identifier, password); Status (active, email verified); Permissions (staff, superuser, groups, permissions; collapsed); Dates (last login, created, updated) |
| Add form | email, full name, password-based authentication on or off, password twice |
| Read-only | public identifier, last login, created at, updated at |
| Inline | the user's memberships, read-only, with a link to each |

Email uniqueness, including different case, is reported as a form error with the
translated message of `unique_user_email_ci`.

The password change page keeps Django's URL name `admin:auth_user_password_change`
(Django's `UserAdmin` names it so for any user model).

## Centers (`CenterAdmin`)

| Aspect | Definition |
| --- | --- |
| Form | `CenterAdminForm`: the languages served are checkboxes (Arabic, English, French) instead of a comma-separated text field. |
| List columns | name, country, review status (badge: amber pending, green approved, red rejected), active, default, created at, and "Review" for users with the change permission |
| Filters | review status, active, default, country |
| Search | name, slug, contact email |
| Slug | prepopulated from the name |
| Fieldsets | main (name, slug, country, logo, description); Contact (contact email, website, Telegram group ID); Service (languages, active, default); Review (status, rejection reason, reviewed at, reviewed by: all read-only); Dates |
| Inline | the center's memberships, read-only, with a link to each |
| Actions | **Approve selected centers**, **Reject selected centers**, **Make selected center the default** |

**Make selected center the default** requires exactly one selected center. With more
or fewer, it shows the error "Select exactly one center to make it the default." and
changes nothing. Otherwise it calls `Center.make_default()` and reports the new default.

Saving a center as default while another one is default, or while it is not approved,
fails form validation with the constraint's translated message; use the action to move
the default. The action refuses a non-approved center.

### Review

Reviews go through `core.services.centers` ([ADR 0013](../architecture/decisions/0013-center-registration-with-review.md)).

- **Review column**: Approve and Reject buttons on pending rows only (Unfold's row actions
  would show on every row). Hidden without the change permission.
- **Change page**: the same buttons at the top of a pending center's page.
- **Dialogs**: each button opens a confirmation dialog (native `dialog` element). The
  Reject dialog requires a reason, shown to the applicant. They post to
  `admin:core_center_approve` and `admin:core_center_reject` (POST only; 405 otherwise;
  403 without the change permission), which redirect back (to a same-host URL only).
- **Bulk actions**: **Approve selected centers** reviews every selected pending center;
  **Reject selected centers** first shows a page asking for the reason. Centers that are
  not pending are skipped and reported. Messages use `ngettext`.

## API keys (`ApiCredentialAdmin`)

Sidebar: **Configuration > API Keys** (icon `vpn_key`, permission `core.view_apicredential`).

| Aspect | Definition |
| --- | --- |
| Add form | `ApiCredentialAddForm`: provider, name, key (password widget, never re-rendered); anti-autofill attributes; `sensitive_post_parameters("secret")` on the add view. Saves through `add_credential`. |
| List columns | name, provider, masked key, active, created at, revoked at |
| Filters | provider, active |
| Detail | read-only: provider, name, masked key, active, created by, created at, revoked at, revoked by |
| Edit | not allowed (403) |
| Action | **Revoke selected API keys** (delete permission; `ngettext` message) |
| Delete | allowed |

Details: [Provider API keys](api-keys.md).

## Questions (`qa/admin.py`)

Every question asked through `POST /api/v1/questions/`, with how the AI answered it
([ADR 0016](../architecture/decisions/0016-question-answering-flow.md)). Read-only: an
`Interaction` is the audit record of one answer, so it is never edited here. Editing an
answer will come with tracked revisions.

| Aspect | Definition |
| --- | --- |
| Help | a "How to read this page" button above the list and above each question's page, opening a dialog (closed with Close, Esc or a click outside): on the list, the decisions with the same coloured badges as the table, levels A to D (D highlighted: always referred), cards for response time, tokens and error, and search; on a page, each section as an illustrated step. Written for first-time readers such as the competition jury (`qa/templates/admin/qa/question/`) |
| List columns | question (first 90 characters), language, decision (badge: green answer, blue partial, amber referred, red abstain and out of scope), level, response time, tokens (in, out), error (badge: red Yes, green No), center, created at |
| Sorting | by decision, level, response time, tokens (input) and created at |
| Filters | decision, level, language, center; date drill-down on created at |
| Search | question text; a pasted follow-up number (`uuid`) finds that exact question |
| Fieldsets | Question (text, public identifier, language, center, session, created at); Answer (decision, level, answer text, kept sentences, removed sentences); Retrieval (search query, ranked results; collapsed); Run (model and prompt version, response time, input and output tokens, error; collapsed) |
| Kept sentences | each sentence the asker saw, its supporting quote (right-to-left) and its Bayyinat question number |
| Removed sentences | each sentence the verification dropped, its quote and the reason: quote not found in the sources (`quote`), or quote does not support the sentence (`entailment`) |
| Question without answer | listed with decision "-"; its page says no answer was saved (the flow failed before saving) |
| Add, change, delete | not allowed (403) |

Text from the model is escaped (`format_html`), never rendered as HTML.
Styles are the `musnid-*` classes in `core/static/core/css/admin.css`, written with logical
properties (`padding-inline-start`, `border-inline-start`) so lists and quote bars flip in
Arabic; Unfold's compiled CSS lacks the utility classes they would otherwise need.

## Knowledge base (`knowledge/admin.py`)

Sidebar group **Knowledge base**: Source documents (with chunk counts) and Source chunks
(filters: kind, document; search: title, text, question number). Read-only: no add, edit
or delete; the embedding is not displayed. Content comes from `ingest_bayyinat`.

## AI settings (`AISettingsAdmin`)

**Configuration > AI settings**: one row (chat model, verifier model, temperature); no
add once it exists, no delete. Defaults: gpt-4o-mini, empty verifier model (= chat model).
Set on 2026-10-04: verifier model gpt-4o ([ADR 0016](../architecture/decisions/0016-question-answering-flow.md)).

## Tokens (`api/admin.py`)

SimpleJWT's `OutstandingTokenAdmin` and `BlacklistedTokenAdmin` combined with Unfold's
`ModelAdmin`, registered in place of SimpleJWT's own, with unchanged behaviour (outstanding
tokens are read-only).

## Memberships (`MembershipAdmin`)

| Aspect | Definition |
| --- | --- |
| Form | `MembershipAdminForm`: on add, user, center and role; on change, role only. Its `clean()` calls `validate_add_member` or `validate_change_role`, so broken rules are form errors. |
| List columns | user, center, role, active, created at, left at |
| Filters | role, active, center |
| Search | user email, user full name, center name |
| Autocomplete | user, center |
| Saving | add: `add_member`; change: `change_role` |
| Read-only on change | public identifier, user, center, active, left at, dates |
| Delete | disabled: no delete action, delete page returns 403 |
| Action | **Offboard selected memberships** |

**Offboard selected memberships** calls `offboard()` for each selected membership. It
reports how many were offboarded and, separately, those refused with the reason (for
example the last active center admin). Both messages use `ngettext`, so singular and
plural forms are translated, including Arabic's six plural forms.

## Groups (`GroupAdmin`)

Django's `GroupAdmin` combined with Unfold's `ModelAdmin`, registered in place of
Django's default so that every admin page uses the same theme.

## Right-to-left

Arabic sets `dir="rtl"` on the page. Unfold 0.108.0 uses physical left/right spacing in
a few places; `core/static/core/css/admin.css` corrects those found by screenshots on
2026-10-04:

| Problem in Arabic | Correction |
| --- | --- |
| Sidebar icons touched their labels (`mr-3`) | margin moved to the left side |
| Login page: theme switcher pushed against "Return to site" (`ml-auto`) | auto margin moved to the right side |
| Login arrows pointed against the reading direction | mirrored |
| Negative Telegram IDs displayed as `1001234567890-` in inputs | number, email and URL inputs are left to right |
| English free text (descriptions) laid out right to left | text inputs and text areas follow their own content (`unicode-bidi: plaintext`) |

In translations, a left-to-right value inside Arabic text (such as the example group ID
in a help text) is wrapped in Unicode isolates (U+2066 … U+2069).
