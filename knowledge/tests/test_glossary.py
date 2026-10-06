"""Tests for knowledge/glossary.py: the official glossary as a separately searched knowledge source."""

from django.test import TestCase

from knowledge.glossary import FIRST_NUMBER, SLUG, TERMS, chunk_text, citation_label, ingest_glossary
from knowledge.models import SourceChunk, SourceDocument
from knowledge.services.ingest import ingest
from knowledge.services.search import get_evidence, search
from knowledge.tests.support import FakeEmbedder, make_question

TAWHID = chunk_text(*TERMS[1])


class GlossaryTests(TestCase):
    """One chunk per term with reserved numbers; searched apart from Bayyinat; usable as evidence."""

    def setUp(self):
        self.embedder = FakeEmbedder()
        ingest([make_question(1)], self.embedder, slug='bayyinat-ar', title='بينات', lang='ar')
        ingest_glossary(self.embedder)

    def test_one_glossary_chunk_per_term_with_reserved_numbers(self):
        document = SourceDocument.objects.get(slug=SLUG)
        chunks = list(document.chunks.order_by('question_number'))
        self.assertEqual(len(chunks), len(TERMS))
        self.assertEqual([c.question_number for c in chunks], list(range(FIRST_NUMBER, FIRST_NUMBER + len(TERMS))))
        self.assertEqual({c.kind for c in chunks}, {SourceChunk.Kind.GLOSSARY})
        self.assertEqual(chunks[1].metadata, {'term': 'التوحيد', 'english': 'Tawhid / Oneness of God'})
        self.assertTrue(chunks[1].text.startswith('التوحيد (Tawhid / Oneness of God): '))
        self.assertIn('page 7', document.license_note)

    def test_ingestion_is_idempotent(self):
        ingest_glossary(self.embedder)
        self.assertEqual(SourceDocument.objects.get(slug=SLUG).chunks.count(), len(TERMS))

    def test_glossary_and_books_are_searched_apart(self):
        terms = search(TAWHID, 3, self.embedder, glossary=True)
        self.assertEqual(terms[0].question_number, FIRST_NUMBER + 1)
        self.assertTrue(all(result.document == SLUG for result in terms))
        self.assertTrue(all(result.document != SLUG for result in search(TAWHID, 8, self.embedder)))

    def test_glossary_chunks_are_evidence_and_have_a_label(self):
        self.assertEqual([c.kind for c in get_evidence([FIRST_NUMBER + 1])], [SourceChunk.Kind.GLOSSARY])
        self.assertEqual(citation_label('التوحيد'), 'نماذج قاموس المصطلحات الأساسية: التوحيد')
