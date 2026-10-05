---
id: translations
title: Translations
sidebar_position: 2
description: How user-facing strings are translated into Arabic and French, the exact commands, and the glossary.
---

# Translations

Every user-facing string (verbose names, help texts, choice labels, error messages) is
written in English, wrapped with `gettext_lazy`, and translated into **Arabic** and
**French** in the same commit. Brand names (Telegram, Musnid) are not translated.

## Configuration

| Setting | Value |
| --- | --- |
| `LANGUAGES` | `ar` Arabic, `en` English, `fr` French |
| `LANGUAGE_CODE` | `en` (source language and fallback) |
| `LOCALE_PATHS` | `locale/` (project), then `locale_vendor/unfold/` (Unfold's strings) |
| Middleware | `LocaleMiddleware`, after `SessionMiddleware` and before `CommonMiddleware` |

`core.models.choices.Language` lists the same three languages; a test fails if the two
drift apart.

Two catalogs, each in Arabic and French, committed as `.po` and compiled `.mo`
([ADR 0009](../architecture/decisions/0009-translations-in-every-change.md)):

| Catalog | Files | Strings (2026-10-04, after the ask API) |
| --- | --- | --- |
| Project | `locale/<lang>/LC_MESSAGES/django.po` | 200 |
| Unfold vendor | `locale_vendor/unfold/<lang>/LC_MESSAGES/django.po` | 131 |

The project catalog comes first in `LOCALE_PATHS`, so for a msgid present in both, the
project's translation wins. Both override the catalogs of installed apps.

## Workflow

GNU gettext must be installed (`brew install gettext` on macOS). Run from the
repository root:

```bash
# 1. Extract strings into both catalogs (the ignores keep the virtualenv out)
.venv/bin/python manage.py makemessages -l ar -l fr \
    --ignore=.venv --ignore=docs --ignore=staticfiles --ignore=media --ignore=data \
    --ignore=locale_vendor

# 2. Translate every new or changed entry in both .po files.
#    Remove any "#, fuzzy" flag after checking the suggested translation.

# 3. Validate format strings and headers
msgfmt --check --statistics -o /dev/null locale/ar/LC_MESSAGES/django.po
msgfmt --check --statistics -o /dev/null locale/fr/LC_MESSAGES/django.po

# 4. Compile
.venv/bin/python manage.py compilemessages --ignore=.venv

# 5. Commit the .po and .mo files together
```

`core/tests/test_translations.py` fails if an entry is untranslated or fuzzy, if a `.mo`
file does not match its `.po` file (step 4 forgotten), or if step 1 would extract
different strings than the committed ones.

## Unfold vendor catalog

django-unfold 0.108.0 ships no translations. Our Arabic and French translations of its
strings live in `locale_vendor/unfold/`, never in `site-packages`. The catalog covers
Unfold's core; `unfold/contrib` (integrations with packages we do not install) is
excluded. It was first filled from Django's own Arabic and French catalogs where the
msgid matched (71 Arabic and 68 French entries), then translated by hand.

After upgrading Unfold, refresh it:

```bash
TMP=$(mktemp -d)
rsync -a --exclude contrib --exclude static --exclude __pycache__ \
    .venv/lib/python3.12/site-packages/unfold/ "$TMP/unfold/"
mkdir "$TMP/unfold/locale"
(cd "$TMP/unfold" && env -u DJANGO_SETTINGS_MODULE "$OLDPWD/.venv/bin/django-admin" makemessages -l ar -l fr)
for lang in ar fr; do
    msgmerge --update --backup=none --no-fuzzy-matching \
        locale_vendor/unfold/$lang/LC_MESSAGES/django.po \
        "$TMP/unfold/locale/$lang/LC_MESSAGES/django.po"
done
rm -rf "$TMP"
# then translate new entries, msgfmt --check, compilemessages, as above
```

Plural forms must match the catalog header: French declares 2, Arabic 6. Django's core
French catalog uses 3; entries reused from it were cut to 2.

## French words identical to English

A French translation equal to its English msgid is treated as untranslated, except for
the words in `FRENCH_SAME_AS_ENGLISH` in `core/tests/test_translations.py`: `Action`,
`API`, `Contact`, `Date`, `Dates`, `Permissions`, `Service`, `avatar`, `description`, `logo`.
Add a word only when French genuinely spells it the same; the test also fails when an
allowlisted word no longer occurs.

## Writing translatable strings

- Use `gettext_lazy as _` in models, forms, settings and module-level constants: they are
  evaluated before a language is active.
- Use named placeholders, never positional ones: `_('“%(role)s” is not a valid role.')`.
  Translators can reorder named placeholders, which Arabic often requires.
- Do not build sentences from fragments; translate whole sentences.
- Messages meant only for developers (exceptions such as `ImproperlyConfigured`,
  `ValueError` in managers) stay in English and are not wrapped.

## Arabic

Arabic is right to left; `translation.get_language_bidi()` returns `True` when it is
active.

- Model names (`verbose_name`) are indefinite (`مركز`, not `المركز`), so counts read
  correctly ("1 مركز"); plural names and headings may take the article (`المراكز`).
- A left-to-right value inside Arabic text, such as `-1001234567890`, is wrapped in the
  Unicode isolates U+2066 and U+2069; otherwise the minus sign is displayed after the
  digits.
- Plural messages need all six forms. When a natural phrasing per form is not practical,
  use one neutral phrasing for all six (for example "عدد العضويات التي أُنهيت: %(count)d.").
  The header generated by `makemessages` already declares the six forms.

## Glossary

Use these terms consistently. Add a row when a new domain term appears.

| English | Arabic | French |
| --- | --- | --- |
| center | مركز | centre |
| default center | المركز الافتراضي | centre par défaut |
| specialist | مختص | spécialiste |
| center admin | مسؤول المركز | administrateur du centre |
| membership | عضوية | adhésion |
| member | عضو | membre |
| role | دور | rôle |
| user | مستخدم | utilisateur |
| email address | البريد الإلكتروني | adresse e-mail |
| public identifier | المعرّف العام | identifiant public |
| referred question | سؤال مُحال | question transmise |
| follow-up number | رقم المتابعة | numéro de suivi |
| asker | السائل | auteur de la question |
| answer revision | مراجعة الجواب | révision de la réponse |
| kept / removed sentences | الجمل المحتفَظ بها / المحذوفة | phrases conservées / retirées |
| active / inactive | نشط / غير نشط | actif / inactif |
| offboard (end a membership) | إنهاء العضوية | mettre fin à l’adhésion |
| accounts | الحسابات | comptes |
| profile | الملف الشخصي | profil |
| deactivate | عطّل | désactiver |
| languages served | اللغات المخدومة | langues prises en charge |
| Telegram | Telegram | Telegram |
