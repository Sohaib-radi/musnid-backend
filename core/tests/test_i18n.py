"""
Tests for internationalisation: settings and the Arabic and French catalogs.

The catalog tests read ``locale/<lang>/LC_MESSAGES/django.po`` directly, so
they fail when a string is left untranslated or fuzzy, and when the compiled
``.mo`` file was not regenerated after the ``.po`` file changed.
"""

import ast
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.utils import translation

TRANSLATED_LANGUAGES = ['ar', 'fr']


def read_po(path):
    """
    Return the entries of a ``.po`` file as dicts with ``msgid``, ``msgstr``
    and ``fuzzy``, skipping the header entry. Handles multi-line strings;
    plural forms and contexts are not used by this project yet.
    """
    entries, entry, field = [], None, None
    for line in Path(path).read_text(encoding='utf-8').splitlines() + ['']:
        line = line.strip()
        if not line:
            if entry and entry.get('msgid'):
                entries.append(entry)
            entry, field = None, None
            continue
        entry = entry or {'msgid': '', 'msgstr': '', 'fuzzy': False}
        if line.startswith('#,') and 'fuzzy' in line:
            entry['fuzzy'] = True
        elif line.startswith(('msgid ', 'msgstr ')):
            field, _sep, literal = line.partition(' ')
            entry[field] = ast.literal_eval(literal)
        elif line.startswith('"') and field:
            entry[field] += ast.literal_eval(line)
    return entries


class SettingsTests(SimpleTestCase):
    """Languages, middleware and catalog location."""

    def test_languages(self):
        self.assertEqual([code for code, _name in settings.LANGUAGES], ['ar', 'en', 'fr'])
        self.assertEqual(settings.LANGUAGE_CODE, 'en')
        self.assertTrue(settings.USE_I18N)

    def test_locale_middleware_follows_sessions_and_precedes_common(self):
        middleware = settings.MIDDLEWARE
        locale = middleware.index('django.middleware.locale.LocaleMiddleware')
        self.assertGreater(locale, middleware.index('django.contrib.sessions.middleware.SessionMiddleware'))
        self.assertLess(locale, middleware.index('django.middleware.common.CommonMiddleware'))

    def test_locale_paths(self):
        self.assertEqual(settings.LOCALE_PATHS, [settings.BASE_DIR / 'locale'])

    def test_arabic_is_right_to_left(self):
        with translation.override('ar'):
            self.assertTrue(translation.get_language_bidi())


class CatalogTests(SimpleTestCase):
    """Every string is translated, and the compiled catalogs are current."""

    def po_path(self, language):
        return settings.BASE_DIR / 'locale' / language / 'LC_MESSAGES' / 'django.po'

    def test_catalogs_exist_and_are_compiled(self):
        for language in TRANSLATED_LANGUAGES:
            with self.subTest(language=language):
                self.assertTrue(self.po_path(language).is_file())
                self.assertTrue(self.po_path(language).with_suffix('.mo').is_file())

    def test_every_string_is_translated_and_not_fuzzy(self):
        for language in TRANSLATED_LANGUAGES:
            entries = read_po(self.po_path(language))
            self.assertTrue(entries)
            for entry in entries:
                with self.subTest(language=language, msgid=entry['msgid']):
                    self.assertTrue(entry['msgstr'], 'untranslated')
                    self.assertFalse(entry['fuzzy'], 'fuzzy')

    def test_compiled_catalogs_match_the_po_files(self):
        for language in TRANSLATED_LANGUAGES:
            with translation.override(language):
                for entry in read_po(self.po_path(language)):
                    with self.subTest(language=language, msgid=entry['msgid']):
                        self.assertEqual(translation.gettext(entry['msgid']), entry['msgstr'])
