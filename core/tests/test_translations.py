"""
Enforcement of the translation rule (ADR 0009): every user-facing string is
available in Arabic and French.

Two catalogs are checked, each in ``ar`` and ``fr``:

* the project catalog, ``locale/<lang>/LC_MESSAGES/django.po``;
* the Unfold vendor catalog, ``locale_vendor/unfold/<lang>/LC_MESSAGES/django.po``,
  our translations of Unfold's own strings (Unfold ships none).

For each: every entry translated and not fuzzy, French entries identical to
English only when allowlisted, the compiled ``.mo`` matching the ``.po``, and
the extraction up to date (a fresh ``makemessages`` on a temporary copy finds
exactly the committed msgids; skipped when GNU gettext is not installed).

Then the strings that reach users are checked where they are used: model and
field labels, choices, admin actions, the sidebar, and rendered admin pages.
"""

import ast
import gettext as gettext_module
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import unfold
from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.test import SimpleTestCase, TestCase
from django.utils import translation
from django_countries.fields import CountryField

from config.unfold import UNFOLD
from core.tests.support import TEST_ONLY_MODELS, make_center, make_user

LANGUAGES = ['ar', 'fr']
PROJECT_LOCALE = settings.BASE_DIR / 'locale'
VENDOR_LOCALE = settings.BASE_DIR / 'locale_vendor' / 'unfold'

# French words spelled exactly like their English msgid. Anything else left
# identical in French is treated as untranslated.
FRENCH_SAME_AS_ENGLISH = {
    'API', 'Action', 'Configuration', 'Contact', 'Date', 'Dates', 'Permissions', 'Question', 'Service', 'URL',
    'document', 'Agents', 'session', 'question', 'questions', 'citations', 'interaction', 'interactions',
    'verdict', 'Questions', '%(seconds).1f s',
    'avatar', 'description', 'logo', 'mode',
}

# Brand names are never translated (in any language), e.g. the OpenAI provider label.
BRAND_NAMES = {'Musnid', 'OpenAI', 'Telegram', 'Unfold'}

# Unfold contrib packages that are not installed: their strings never render,
# so they are left out of the vendor catalog.
UNFOLD_EXCLUDED_DIRS = ['contrib', 'static']

MAKEMESSAGES_IGNORES = [
    '--ignore=.venv', '--ignore=docs', '--ignore=staticfiles', '--ignore=media',
    '--ignore=data', '--ignore=locale_vendor',
]


def read_po(path):
    """
    Parse a ``.po`` file into a list of entry dicts.

    Each dict has ``msgctxt``, ``msgid``, ``msgid_plural``, ``msgstr`` (a list:
    one item, or one per plural form) and ``fuzzy``. The header and obsolete
    (``#~``) entries are skipped. Enough of the format for catalogs written by
    ``makemessages``; not a general-purpose parser.
    """
    entries = []
    entry, field = None, None

    def flush():
        if entry and entry['msgid']:
            entries.append(entry)

    for raw in Path(path).read_text(encoding='utf-8').splitlines() + ['']:
        line = raw.strip()
        if not line:
            flush()
            entry, field = None, None
            continue
        if line.startswith('#~'):
            continue
        if entry is None:
            entry = {'msgctxt': None, 'msgid': '', 'msgid_plural': None, 'msgstr': {}, 'fuzzy': False}
        if line.startswith('#,'):
            entry['fuzzy'] = entry['fuzzy'] or 'fuzzy' in line
            continue
        if line.startswith('#'):
            continue
        if line.startswith('"'):
            value = ast.literal_eval(line)
            if isinstance(field, int):
                entry['msgstr'][field] += value
            else:
                entry[field] += value
            continue
        keyword, _sep, literal = line.partition(' ')
        value = ast.literal_eval(literal)
        if keyword.startswith('msgstr['):
            field = int(keyword[7:-1])
            entry['msgstr'][field] = value
        elif keyword == 'msgstr':
            field = 0
            entry['msgstr'][0] = value
        else:
            field = keyword
            entry[field] = value
    for item in entries:
        item['msgstr'] = [item['msgstr'][index] for index in sorted(item['msgstr'])]
    return entries


def po_path(locale_root, language):
    return Path(locale_root) / language / 'LC_MESSAGES' / 'django.po'


def msgids(path):
    return {(entry['msgctxt'], entry['msgid']) for entry in read_po(path)}


CATALOGS = {'project': PROJECT_LOCALE, 'unfold': VENDOR_LOCALE}


class CatalogTests(SimpleTestCase):
    """Both catalogs are complete, compiled and free of untranslated copies."""

    def test_every_entry_is_translated_and_not_fuzzy(self):
        for name, root in CATALOGS.items():
            for language in LANGUAGES:
                entries = read_po(po_path(root, language))
                self.assertTrue(entries, f'{name}/{language} is empty')
                for entry in entries:
                    with self.subTest(catalog=name, language=language, msgid=entry['msgid']):
                        self.assertTrue(all(entry['msgstr']), 'untranslated')
                        self.assertFalse(entry['fuzzy'], 'fuzzy')

    def test_french_matches_english_only_when_allowlisted(self):
        for name, root in CATALOGS.items():
            for entry in read_po(po_path(root, 'fr')):
                if entry['msgstr'][0] == entry['msgid']:
                    with self.subTest(catalog=name, msgid=entry['msgid']):
                        self.assertIn(entry['msgid'], FRENCH_SAME_AS_ENGLISH)

    def test_arabic_never_matches_english(self):
        for name, root in CATALOGS.items():
            for entry in read_po(po_path(root, 'ar')):
                with self.subTest(catalog=name, msgid=entry['msgid']):
                    self.assertNotEqual(entry['msgstr'][0], entry['msgid'])

    def test_allowlist_has_no_stale_entries(self):
        identical = {
            entry['msgid']
            for root in CATALOGS.values()
            for entry in read_po(po_path(root, 'fr'))
            if entry['msgstr'][0] == entry['msgid']
        }
        self.assertEqual(FRENCH_SAME_AS_ENGLISH - identical, set())

    def test_compiled_catalogs_match_the_po_files(self):
        # Each .mo is read on its own, so a msgid present in both catalogs
        # cannot hide a stale file behind the other one.
        for name, root in CATALOGS.items():
            for language in LANGUAGES:
                path = po_path(root, language)
                with path.with_suffix('.mo').open('rb') as handle:
                    compiled = gettext_module.GNUTranslations(handle)
                for entry in read_po(path):
                    with self.subTest(catalog=name, language=language, msgid=entry['msgid']):
                        if entry['msgid_plural']:
                            got = compiled.ngettext(entry['msgid'], entry['msgid_plural'], 1)
                            self.assertIn(got, entry['msgstr'])
                        else:
                            self.assertEqual(compiled.gettext(entry['msgid']), entry['msgstr'][0])


class ExtractionTests(SimpleTestCase):
    """The committed catalogs contain exactly what ``makemessages`` extracts today."""

    def setUp(self):
        if shutil.which('xgettext') is None or shutil.which('msguniq') is None:
            self.skipTest('GNU gettext is not installed')

    def extract(self, source_dir, extra_args=()):
        """Run makemessages for ar and fr in ``source_dir``; return its locale dir."""
        (source_dir / 'locale').mkdir(exist_ok=True)
        subprocess.run(
            [sys.executable, '-m', 'django', 'makemessages', '-l', 'ar', '-l', 'fr', *extra_args],
            cwd=source_dir, check=True, capture_output=True, timeout=300,
            # No DJANGO_SETTINGS_MODULE: makemessages then configures minimal
            # settings itself and writes to ./locale, independent of .env.
            env={'PATH': os.environ['PATH']},
        )
        return source_dir / 'locale'

    def test_project_catalog_is_up_to_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp)
            for name in ('config', 'core', 'api', 'knowledge', 'qa', 'agents', 'telegram_bot'):
                shutil.copytree(settings.BASE_DIR / name, copy / name, ignore=shutil.ignore_patterns('__pycache__', 'static'))
            extracted = self.extract(copy, MAKEMESSAGES_IGNORES)
            for language in LANGUAGES:
                with self.subTest(language=language):
                    self.assertEqual(
                        msgids(po_path(extracted, language)),
                        msgids(po_path(PROJECT_LOCALE, language)),
                        'run makemessages and translate the new strings',
                    )

    def test_unfold_vendor_catalog_is_up_to_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / 'unfold'
            shutil.copytree(
                Path(unfold.__file__).parent, copy,
                ignore=shutil.ignore_patterns('__pycache__', *UNFOLD_EXCLUDED_DIRS),
            )
            extracted = self.extract(copy)
            for language in LANGUAGES:
                with self.subTest(language=language):
                    self.assertEqual(
                        msgids(po_path(extracted, language)),
                        msgids(po_path(VENDOR_LOCALE, language)),
                        'Unfold strings changed: refresh locale_vendor/unfold',
                    )


def english_and(language, value):
    """Return ``value`` rendered in English and in ``language``."""
    with translation.override('en'):
        english = str(value)
    with translation.override(language):
        return english, str(value)


class UsedStringsTests(SimpleTestCase):
    """Strings reach users translated where they are used, not only in catalogs."""

    def assertTranslated(self, value, label):
        for language in LANGUAGES:
            english, translated = english_and(language, value)
            with self.subTest(label=label, language=language, english=english):
                if english in BRAND_NAMES or (language == 'fr' and english in FRENCH_SAME_AS_ENGLISH):
                    continue
                self.assertNotEqual(translated, english)

    def test_model_names_field_labels_and_choices(self):
        for model in apps.get_app_config('core').get_models():
            if model in TEST_ONLY_MODELS:
                continue
            self.assertTranslated(model._meta.verbose_name, f'{model.__name__} verbose_name')
            self.assertTranslated(model._meta.verbose_name_plural, f'{model.__name__} verbose_name_plural')
            for field in model._meta.get_fields():
                if field.auto_created and not field.concrete:
                    continue  # reverse relations have no label of their own
                if field.name == 'id':
                    continue  # never shown
                self.assertTranslated(field.verbose_name, f'{model.__name__}.{field.name}')
                # Country names come translated from django-countries, and many
                # are spelled the same in French; only our own choices are checked.
                if isinstance(field, CountryField):
                    continue
                base_field = getattr(field, 'base_field', field)  # ArrayField items
                for _value, choice_label in getattr(base_field, 'choices', None) or []:
                    self.assertTranslated(choice_label, f'{model.__name__}.{field.name} choice')

    def test_admin_actions(self):
        for model, model_admin in admin.site._registry.items():
            for action_name in model_admin.actions or []:
                function = getattr(model_admin, action_name)
                self.assertTranslated(function.short_description, f'{model.__name__} action {action_name}')

    def test_sidebar(self):
        for group in UNFOLD['SIDEBAR']['navigation']:
            self.assertTranslated(group['title'], 'sidebar group')
            for item in group['items']:
                self.assertTranslated(item['title'], 'sidebar item')


class RenderedPagesTests(TestCase):
    """Key admin pages render translated in Arabic (right to left) and French."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = make_user(is_staff=True, is_superuser=True)
        cls.center = make_center(name='Dar al-Ifta')

    def setUp(self):
        # LocaleMiddleware activates the request's language on this thread and
        # does not reset it; restore the default so later tests see English.
        self.addCleanup(translation.activate, settings.LANGUAGE_CODE)

    def get(self, url, language):
        return self.client.get(url, HTTP_ACCEPT_LANGUAGE=language)

    def test_login_page(self):
        expectations = {
            'ar': ('dir="rtl"', 'مرحبًا بعودتك إلى'),
            'fr': ('dir="ltr"', 'Bon retour sur'),
        }
        for language, texts in expectations.items():
            with self.subTest(language=language):
                response = self.get('/admin/login/', language)
                for text in texts:
                    self.assertContains(response, text)

    def test_center_pages(self):
        self.client.force_login(self.superuser)
        pages = [
            ('/admin/core/center/', {'ar': ['المراكز', 'جعل المركز المحدد هو المركز الافتراضي'],
                                     'fr': ['Centres', 'Définir le centre sélectionné comme centre par défaut']}),
            (f'/admin/core/center/{self.center.pk}/change/', {'ar': ['اللغات المخدومة', 'معرّف مجموعة Telegram'],
                                                             'fr': ['langues prises en charge', 'ID du groupe Telegram']}),
        ]
        for url, expected in pages:
            for language, texts in expected.items():
                with self.subTest(url=url, language=language):
                    response = self.get(url, language)
                    self.assertContains(response, 'dir="rtl"' if language == 'ar' else 'dir="ltr"')
                    for text in texts:
                        self.assertContains(response, text)

    def test_sidebar_is_translated(self):
        self.client.force_login(self.superuser)
        response = self.get('/admin/', 'ar')
        for text in ('المراكز', 'العضويات', 'الحسابات', 'المستخدمون', 'المجموعات'):
            self.assertContains(response, text)
