"""Tests for knowledge/services: ingestion and search, with a fake embedder."""

from unittest import mock

from django.db import connection
from django.test import TestCase

from knowledge.models import SourceChunk, SourceDocument
from knowledge.services.ingest import ingest
from knowledge.services.search import get_evidence, search
from knowledge.tests.support import FakeEmbedder, make_question

QUESTIONS = [
    make_question(1),
    make_question(2, title='لماذا خلقنا الله؟', question='ما الحكمة من خلق الإنسان؟',
                  alternative_phrasings=['ما الغاية من الخلق؟'],
                  answer_sections={'summary': 'لعبادة الله.', 'detailed': 'تفصيل الحكمة من الخلق.'},
                  answer_summary='لعبادة الله.'),
]


def run_ingest(embedder=None, questions=QUESTIONS):
    return ingest(questions, embedder or FakeEmbedder(), slug='bayyinat-ar', title='بينات', lang='ar')


class IngestTests(TestCase):
    """Idempotent by slug; embeddings before the old chunks are deleted."""

    def test_stores_document_and_chunks(self):
        document, count = run_ingest()
        self.assertEqual(count, SourceChunk.objects.count())
        self.assertEqual(SourceChunk.objects.filter(kind='question').count(), 2)
        chunk = SourceChunk.objects.filter(kind='summary', question_number=1).get()
        self.assertEqual(chunk.text_norm, 'هل انتشر الاسلام بالسيف؟\nلم ينتشر الاسلام بالسيف.'.replace('\n', ' '))
        self.assertEqual(document.slug, 'bayyinat-ar')

    def test_stores_the_public_urls(self):
        document, _count = ingest(QUESTIONS, FakeEmbedder(), slug='bayyinat-ar', title='بينات', lang='ar',
                                  url='https://example.org/book', pdf_url='https://example.org/book.pdf')
        document.refresh_from_db()
        self.assertEqual((document.url, document.pdf_url), ('https://example.org/book', 'https://example.org/book.pdf'))

    def test_embeds_normalized_text_in_one_call(self):
        embedder = FakeEmbedder()
        run_ingest(embedder)
        self.assertEqual(len(embedder.calls), 1)
        self.assertNotIn('ِ', ''.join(embedder.calls[0]))

    def test_rerun_replaces_chunks(self):
        run_ingest()
        run_ingest(questions=QUESTIONS[:1])
        self.assertEqual(SourceDocument.objects.count(), 1)
        self.assertEqual(set(SourceChunk.objects.values_list('question_number', flat=True)), {1})

    def test_failed_embedding_keeps_previous_chunks(self):
        run_ingest()
        before = SourceChunk.objects.count()
        with self.assertRaises(RuntimeError):
            run_ingest(FakeEmbedder(fail=True), questions=QUESTIONS[:1])
        self.assertEqual(SourceChunk.objects.count(), before)


class SearchTests(TestCase):
    """Best chunk per question, cosine score, evidence without question chunks."""

    def setUp(self):
        self.embedder = FakeEmbedder()
        run_ingest(self.embedder)

    def test_best_chunk_per_question(self):
        results = search('هل انتشر الإسلام بالسيف؟', 5, self.embedder)
        self.assertEqual([r.question_number for r in results], [1, 2])
        self.assertGreater(results[0].score, results[1].score)
        self.assertLessEqual(results[0].score, 1.0001)

    def test_query_is_normalized(self):
        with_marks = search('هَلْ انتشرَ الإسلامُ بالسيفِ؟', 1, self.embedder)[0]
        without = search('هل انتشر الاسلام بالسيف؟', 1, self.embedder)[0]
        self.assertAlmostEqual(with_marks.score, without.score)

    def test_k_limits_results(self):
        self.assertEqual(len(search('الإسلام', 1, self.embedder)), 1)

    def test_ef_search_is_raised_to_the_candidate_count(self):
        executed = []
        original = connection.cursor

        def spy():
            cursor = original()
            real_execute = cursor.execute
            cursor.execute = lambda sql, params=None: (executed.append((sql, params)), real_execute(sql, params))[1]
            return cursor
        with mock.patch.object(connection, 'cursor', spy):
            search('الإسلام', 10, self.embedder)
        self.assertIn(('SET LOCAL hnsw.ef_search = %s', [80]), executed)

    def test_get_evidence(self):
        evidence = get_evidence([2, 1])
        self.assertNotIn(SourceChunk.Kind.QUESTION, [c.kind for c in evidence])
        self.assertEqual([(c.question_number, c.kind) for c in evidence][:2], [(2, 'summary'), (2, 'answer')])
        self.assertEqual(evidence[2].question_number, 1)
        positions = [c.metadata['position'] for c in evidence if c.question_number == 1]
        self.assertEqual(positions, sorted(positions))


class SourceDocumentUrlTests(TestCase):
    """Links to the book page (interface language) and to a page of the PDF."""

    def document(self, **fields):
        return SourceDocument(slug='b', title='B', lang='ar', **fields)

    def test_page_url_adds_a_supported_language(self):
        document = self.document(url='https://dawa.center/file/7937')
        self.assertEqual(document.page_url('fr'), 'https://dawa.center/file/7937?lang=fr')
        self.assertEqual(document.page_url('de'), 'https://dawa.center/file/7937')
        self.assertEqual(document.page_url(''), 'https://dawa.center/file/7937')

    def test_page_url_keeps_an_existing_query(self):
        self.assertEqual(self.document(url='https://x.org/f?id=1').page_url('ar'), 'https://x.org/f?id=1&lang=ar')

    def test_pdf_page_url_counts_viewer_pages_from_one(self):
        document = self.document(pdf_url='https://x.org/book.pdf')
        self.assertEqual(document.pdf_page_url(1074), 'https://x.org/book.pdf#page=1075')
        self.assertEqual(document.pdf_page_url(None), 'https://x.org/book.pdf')

    def test_empty_without_urls(self):
        self.assertEqual((self.document().page_url('ar'), self.document().pdf_page_url(3)), ('', ''))
