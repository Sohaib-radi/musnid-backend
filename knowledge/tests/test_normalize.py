"""Tests for knowledge/normalize.py: one test per rule, named by Unicode name."""

import unicodedata

from django.test import SimpleTestCase

from knowledge.normalize import normalize


class NormalizeTests(SimpleTestCase):
    """Lucene ArabicNormalizer direction."""

    def assertMaps(self, source, target):
        with self.subTest(char=unicodedata.name(source)):
            self.assertEqual(normalize(f'ب{source}ب'), f'ب{target}ب')

    def test_alef_with_madda_above_to_alef(self):
        self.assertMaps('آ', 'ا')

    def test_alef_with_hamza_above_to_alef(self):
        self.assertMaps('أ', 'ا')

    def test_alef_with_hamza_below_to_alef(self):
        self.assertMaps('إ', 'ا')

    def test_alef_wasla_to_alef(self):
        self.assertMaps('ٱ', 'ا')

    def test_teh_marbuta_to_heh(self):
        self.assertMaps('ة', 'ه')

    def test_alef_maksura_to_yeh(self):
        self.assertMaps('ى', 'ي')

    def test_tatweel_removed(self):
        self.assertMaps('ـ', '')

    def test_harakat_removed(self):
        for code in range(0x064B, 0x0653):  # FATHATAN .. SUKUN
            self.assertMaps(chr(code), '')

    def test_superscript_alef_removed(self):
        self.assertMaps('ٰ', '')

    def test_whitespace_and_example(self):
        self.assertEqual(normalize('  هَلِ انتشرَ الإسلامُ   بالسَّيفِ؟ '), 'هل انتشر الاسلام بالسيف؟')
