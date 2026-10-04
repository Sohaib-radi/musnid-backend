"""Tests for the shared enumerations in ``core.models.choices``."""

from django.conf import settings
from django.test import SimpleTestCase

from core.models import Language


class LanguageTests(SimpleTestCase):
    """``Language`` must stay in sync with ``settings.LANGUAGES``."""

    def test_codes_match_settings_languages(self):
        self.assertEqual(Language.values, [code for code, _name in settings.LANGUAGES])

    def test_labels_match_settings_languages(self):
        self.assertEqual(
            [str(label) for label in Language.labels],
            [str(name) for _code, name in settings.LANGUAGES],
        )
