"""Tests for knowledge/chunking.py."""

from django.test import SimpleTestCase

from knowledge.chunking import TARGET_WORDS, chunk_question, split_words
from knowledge.tests.support import make_question


class SplitWordsTests(SimpleTestCase):
    """Pieces of about 400 words on paragraph boundaries."""

    def test_short_text_is_one_piece(self):
        self.assertEqual(split_words('أ ب\nج د'), ['أ ب\nج د'])

    def test_paragraphs_are_not_split_when_they_fit(self):
        paragraph = ' '.join(['كلمة'] * 300)
        pieces = split_words(f'{paragraph}\n{paragraph}')
        self.assertEqual([len(p.split()) for p in pieces], [300, 300])

    def test_long_paragraph_is_cut_on_words(self):
        pieces = split_words(' '.join(['كلمة'] * (TARGET_WORDS * 2 + 10)))
        self.assertEqual([len(p.split()) for p in pieces], [TARGET_WORDS, TARGET_WORDS, 10])


class ChunkQuestionTests(SimpleTestCase):
    """One question chunk, one summary chunk, answer chunks prefixed with the title."""

    def test_chunks(self):
        chunks = chunk_question(make_question())
        kinds = [c.kind for c in chunks]
        self.assertEqual(kinds, ['question', 'summary', 'answer', 'answer', 'answer'])
        question = chunks[0]
        self.assertIn('هل أكره الناس على الإسلام؟', question.text)
        self.assertIn('يقال إن الإسلام انتشر بالقوة.', question.text)
        for chunk in chunks[1:]:
            self.assertTrue(chunk.text.startswith('هل انتشر الإسلام بالسيف؟\n'))
        self.assertEqual([c.metadata['section'] for c in chunks[2:]], ['content', 'detailed', 'conclusion'])
        self.assertEqual([c.metadata['position'] for c in chunks[2:]], [1, 2, 3])

    def test_question_without_summary(self):
        chunks = chunk_question(make_question(answer_summary=''))
        self.assertNotIn('summary', [c.kind for c in chunks])
