"""Tests for knowledge/extraction/bayyinat.py and the extract command's isolation."""

import importlib
import sys

from django.test import SimpleTestCase

from knowledge.extraction.bayyinat import EXPECTED_QUESTIONS, Line, parse, validate


def lines():
    return [
        Line(5, 50, 'part', 'أولًا: الإيمان بالله'),
        Line(5, 70, 'chapter', '1- توحيد الربوبية'),
        Line(5, 90, 'title', 'إنكار وجود الله'),
        Line(5, 110, 'label', 'السؤال'),
        Line(5, 130, 'body', 'لماذا نؤمن؟'),
        Line(5, 150, 'sublabel', 'عبارات مشابهة للسؤال'),
        Line(5, 170, 'body', 'الصيغة الأولى', bullet=True),
        Line(5, 192, 'body', 'تكملة', bullet=False),
        Line(5, 214, 'body', 'الصيغة الثانية', bullet=True),
        Line(5, 240, 'label', 'الجواب'),
        Line(5, 260, 'sublabel', ':مختصر الإجابة'),
        Line(5, 280, 'body', 'سطر أول'),
        Line(5, 302, 'body', 'سطر ثان'),
        Line(5, 340, 'body', 'فقرة جديدة'),
        Line(6, 60, 'sublabel', ':الجواب التفصيلي'),
        Line(6, 80, 'body', 'تفصيل'),
        Line(7, 50, 'title', 'السؤال الثاني'),
    ]


class ParseTests(SimpleTestCase):
    """Questions are assembled from classified lines."""

    def test_structure(self):
        first, second = parse(lines())
        self.assertEqual((first['number'], second['number']), (1, 2))
        self.assertEqual(first['part'], 'أولًا: الإيمان بالله')
        self.assertEqual(first['chapter'], '1- توحيد الربوبية')
        self.assertEqual(first['question'], 'لماذا نؤمن؟')
        self.assertEqual(first['alternative_phrasings'], ['الصيغة الأولى تكملة', 'الصيغة الثانية'])
        self.assertEqual(first['answer_summary'], 'سطر أول سطر ثان\nفقرة جديدة')
        self.assertEqual(first['answer_sections']['detailed'], 'تفصيل')
        self.assertEqual((first['page_start'], first['page_end']), (5, 6))
        self.assertEqual(second['part'], 'أولًا: الإيمان بالله')

    def test_two_title_lines_make_one_title(self):
        questions = parse([Line(1, 10, 'title', 'الجزء الأول'), Line(1, 30, 'title', 'من العنوان')])
        self.assertEqual([q['title'] for q in questions], ['الجزء الأول من العنوان'])


class ValidateTests(SimpleTestCase):
    """Warnings for missing parts and unrepaired ligatures."""

    def test_warnings(self):
        warnings = validate(parse(lines()))
        self.assertIn(f'expected {EXPECTED_QUESTIONS} questions, found 2', warnings)
        self.assertIn('question 2: empty question', warnings)
        self.assertNotIn('question 1: empty question', warnings)

    def test_unrepaired_ligature_is_reported(self):
        questions = parse(lines())
        questions[0]['answer_sections']['detailed'] = 'اإليمان'
        self.assertIn('question 1: possible unrepaired ligature', validate(questions))


class PyMuPdfIsolationTests(SimpleTestCase):
    """PyMuPDF (AGPL) is imported only inside the command's handle()."""

    def test_command_module_does_not_import_pymupdf(self):
        sys.modules.pop('pymupdf', None)
        importlib.reload(importlib.import_module('knowledge.management.commands.extract_bayyinat'))
        self.assertNotIn('pymupdf', sys.modules)

    def test_pymupdf_is_not_a_runtime_requirement(self):
        from django.conf import settings
        requirements = (settings.BASE_DIR / 'requirements.txt').read_text().lower()
        self.assertNotIn('pymupdf', requirements)
