---
id: 0009-translations-in-every-change
title: "ADR 0009: Translations in every change"
sidebar_position: 9
description: Why every user-facing string ships in Arabic and French in the same commit, and how the tests enforce it.
---

# ADR 0009: Translations in every change

## Status

Accepted, 2026-10-04.

## Context

The platform serves Arabic, French and English speakers. A string that reaches users in
English only is a defect for most of them. Translation done "later" accumulates, and
untranslated strings are hard to find by reading the code. Third-party packages may ship
partial translations or none: django-unfold 0.108.0 ships no `locale/` directory at all.

## Decision

Every user-facing string is translated into Arabic and French **in the same commit**
that adds or changes it. Brand names (Musnid, Unfold, Telegram) are not translated.

Two catalogs, both committed as `.po` and compiled `.mo`:

| Catalog | Path | Content |
| --- | --- | --- |
| Project | `locale/<lang>/LC_MESSAGES/` | Strings in `config/` and `core/`. |
| Unfold vendor | `locale_vendor/unfold/<lang>/LC_MESSAGES/` | Our translations of Unfold's strings. |

`LOCALE_PATHS` lists the project catalog first, then the vendor catalog; both take
precedence over the catalogs of installed apps. Vendor strings are never translated by
editing `site-packages`, which an upgrade or reinstall would silently undo. Where
Django already translates an Unfold string, the vendor catalog starts from Django's
translation, for consistent wording.

**Enforcement** (`core/tests/test_translations.py`), for both catalogs and both languages:

1. Every entry translated, none fuzzy.
2. Arabic never identical to English; French identical to English only for words in an
   explicit allowlist (`FRENCH_SAME_AS_ENGLISH`, e.g. "Permissions", "Date"). The
   allowlist itself must not contain entries that no longer occur.
3. Each compiled `.mo` matches its `.po` (read file by file, so one catalog cannot mask
   the other).
4. Extraction is current: `makemessages` is run on a temporary copy of the project and of
   Unfold, and must find exactly the committed msgids. Skipped when GNU gettext is not
   installed.
5. Every model and field label, our choice labels, admin action and sidebar item renders
   differently in Arabic and French than in English (allowlist aside).
6. Key admin pages, rendered in Arabic (`dir="rtl"`) and French, contain the expected
   translated text.

## Consequences

- A change with a new string fails the test suite until both catalogs are updated and
  compiled, so the rule does not depend on review.
- Developers need GNU gettext to update catalogs; without it, check 4 is skipped but the
  others still run.
- Upgrading Unfold requires refreshing `locale_vendor/unfold` (check 4 fails when its
  strings change). Workflow: [Translations](../../development/translations.md).
- Unfold integrations that are not installed (`unfold/contrib`) are excluded from the
  vendor catalog; enabling one means adding its strings.
- Translations are written by the development team and still need review by native
  speakers.
