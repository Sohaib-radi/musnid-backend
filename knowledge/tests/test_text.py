"""Tests for knowledge/extraction/text.py: rebuilding logical Arabic lines."""

from django.test import SimpleTestCase

from knowledge.extraction.text import QURAN_MARK, fix_text, group_lines, line_text


def char(c, x0, x1, y=100.0):
    return {'c': c, 'x0': x0, 'x1': x1, 'y': y}


class LineTextTests(SimpleTestCase):
    """Right-to-left ordering and ligature repair from character boxes."""

    def test_characters_are_ordered_right_to_left(self):
        chars = [char('.', 10, 12), char('ب', 30, 35), char('ا', 40, 45)]
        self.assertEqual(line_text(chars), 'اب.')

    def test_zero_width_alef_before_lam_is_a_ligature(self):
        # "الإيمان" as extracted: article alef, zero-width hamza-alef, lam.
        chars = [char('ا', 267.1, 272.0), char('إ', 267.1, 267.1), char('ل', 252.1, 267.1),
                 char('ي', 243.6, 252.1), char('م', 232.6, 243.6), char('ا', 227.1, 232.6),
                 char('ن', 213.9, 227.1)]
        self.assertEqual(line_text(chars), 'الإيمان')

    def test_alef_with_width_is_not_a_ligature(self):
        chars = [char('س', 414.2, 426.5), char('ؤ', 406.5, 414.2), char('ا', 403.0, 406.5), char('ل', 394.3, 403.0)]
        self.assertEqual(line_text(chars), 'سؤال')

    def test_group_lines_by_baseline(self):
        lines = group_lines([char('a', 0, 1, 100), char('b', 0, 1, 101.5), char('c', 0, 1, 130)])
        self.assertEqual([[c['c'] for c in line] for line in lines], [['a', 'b'], ['c']])


class FixTextTests(SimpleTestCase):
    """Text-level repairs."""

    def test_allah_ligature_forms(self):
        self.assertEqual(fix_text('وجودِ هللاِ'), 'وجودِ اللهِ')
        self.assertEqual(fix_text('باهلل'), 'بالله')

    def test_tanween_alef(self):
        cases = {'أولً': 'أولًا', 'جدًّا': 'جدًّا', 'هدًى': 'هدًى', 'رحمةً': 'رحمةً', 'سماءً': 'سماءً'}
        for extracted, expected in cases.items():
            with self.subTest(extracted=extracted):
                self.assertEqual(fix_text(extracted), expected)

    def test_double_lam_alef(self):
        self.assertEqual(fix_text('الدَّلاالت'), 'الدَّلالات')

    def test_ltr_runs_are_reversed_back(self):
        # Right-to-left ordering reverses digit runs; fix_text restores them.
        self.assertEqual(fix_text('سنة 0202'), 'سنة 2020')

    def test_mirrored_brackets_are_swapped(self):
        self.assertEqual(fix_text(')يس: 04('), '(يس: 40)')

    def test_quran_runs_become_one_placeholder(self):
        self.assertEqual(fix_text(f'﴿{QURAN_MARK}{QURAN_MARK} {QURAN_MARK}﴾'), '﴿ [آية] ﴾')
