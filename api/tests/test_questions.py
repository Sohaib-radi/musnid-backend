"""Tests for anonymous asking: /api/v1/questions/ (ADR 0017). The flow is replaced by a fake ``ask``."""

import uuid
from unittest import mock

from django.conf import settings
from django.db import connection
from django.test import override_settings

from agents.replies import fixed_reply
from agents.services import DailyLimitReached
from api.tests.base import APITestCase
from core.tests.support import make_center
from knowledge.services.ingest import ingest
from knowledge.tests.support import FakeEmbedder, make_question
from qa.models import Interaction, Question

SESSION = 'session-0001'
QUESTION = 'هل انتشر الإسلام بالسيف؟'
QUOTE = 'الإسلامُ لم ينتشِرْ بالسيف، وإنما انتشَرَ بالدعوةِ والحُجَّة'
BOOK = 'https://dawa.center/file/7937'
PDF = 'https://dawa.center/storage/files/book.pdf'


class QuestionAPITestCase(APITestCase):
    """A default center, Bayyinat #229 in the knowledge base, and a fake ``ask``."""

    def setUp(self):
        super().setUp()
        self.center = make_center(is_default=True)
        ingest([make_question(229, title=QUESTION, page_start=1074, page_end=1081)], FakeEmbedder(),
               slug='bayyinat-ar', title='بينات', lang='ar', url=BOOK, pdf_url=PDF)
        self.calls = []

    def saved(self, text=QUESTION, session_id=SESSION, lang='ar', decision='answer', level='B',
              sentences=None, dropped=None, answer='الإسلام لم ينتشر بالسيف [Q229].'):
        """Save a question and its interaction as ``agents.services.ask`` would."""
        question = Question.objects.create(center=self.center, text=text, lang=lang, session_id=session_id)
        if sentences is None:
            sentences = [{'text': 'الإسلام لم ينتشر بالسيف.', 'quote': QUOTE, 'number': 229}]
        return Interaction.objects.create(question=question, decision=decision, level=level, answer_text=answer,
                                          sentences=sentences, dropped=dropped or [])

    def fake_ask(self, **outcome):
        """A replacement for ``ask`` that records its arguments and saves ``outcome``."""
        def ask(text, session_id=''):
            self.calls.append((text, session_id))
            return self.saved(text=text, session_id=session_id, **outcome)
        return mock.patch('agents.services.ask', side_effect=ask)

    def post(self, text=QUESTION, session_id=SESSION, **extra):
        return self.client.post(self.url('questions'), {'text': text, 'session_id': session_id}, format='json',
                                **extra)


class AskTests(QuestionAPITestCase):
    """POST /questions/: no login, the response format, refer, limits on input."""

    def test_anonymous_answer_with_sentences_sources_and_notes(self):
        dropped = [{'text': 'a', 'quote': 'b', 'reason': 'quote'}, {'text': 'c', 'quote': 'd', 'reason': 'entailment'}]
        with self.fake_ask(decision='partial', level='C', dropped=dropped):
            response = self.post()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.calls, [(QUESTION, SESSION)])
        data = response.data
        self.assertEqual(list(data), ['uuid', 'session_id', 'text', 'language', 'level', 'decision', 'answer',
                                      'sentences', 'notes', 'verification', 'follow_up_number', 'created_at'])
        self.assertEqual(data['uuid'], str(Question.objects.get().uuid))
        self.assertEqual((data['language'], data['level'], data['decision']), ('ar', 'C', 'partial'))
        self.assertEqual(data['sentences'], [{
            'text': 'الإسلام لم ينتشر بالسيف.', 'quote': QUOTE,
            'source': {'number': 229, 'title': QUESTION, 'pages': {'start': 1074, 'end': 1081},
                       'url': f'{BOOK}?lang=ar', 'pdf_url': f'{PDF}#page=1075'},
        }])
        self.assertEqual(data['notes'], [{'code': 'partial', 'text': fixed_reply('partial', 'ar')},
                                         {'code': 'level_c', 'text': fixed_reply('disagreement', 'ar')}])
        self.assertEqual(data['verification'], {'kept': 1, 'removed': 2})
        self.assertIsNone(data['follow_up_number'])

    def test_book_link_follows_the_question_language(self):
        with self.fake_ask(lang='fr'):
            response = self.post()
        self.assertEqual(response.data['sentences'][0]['source']['url'], f'{BOOK}?lang=fr')

    def test_referral_returns_the_uuid_as_follow_up_number(self):
        with self.fake_ask(decision='refer', level='D', sentences=[], answer=fixed_reply('refer', 'ar')):
            response = self.post()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['follow_up_number'], response.data['uuid'])
        self.assertEqual((response.data['sentences'], response.data['notes']), ([], []))

    def test_source_missing_from_the_knowledge_base_is_empty_not_an_error(self):
        with self.fake_ask(sentences=[{'text': 't', 'quote': 'q', 'number': 999}]):
            response = self.post()
        self.assertEqual(response.data['sentences'][0]['source'],
                         {'number': 999, 'title': '', 'pages': None, 'url': '', 'pdf_url': ''})

    def test_a_stale_token_does_not_block_asking(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer not-a-token')
        with self.fake_ask():
            self.assertEqual(self.post().status_code, 201)
        self.assertEqual(self.client.get(self.url('questions'), {'session_id': SESSION}).status_code, 200)

    def test_invalid_input_is_rejected_with_codes(self):
        cases = [
            ({'text': 'ab', 'session_id': SESSION}, {'text': ['min_length']}),
            ({'text': 'x' * 2001, 'session_id': SESSION}, {'text': ['max_length']}),
            ({'text': QUESTION, 'session_id': 'short'}, {'session_id': ['invalid']}),
            ({'text': QUESTION, 'session_id': 'has space in it'}, {'session_id': ['invalid']}),
            ({'text': QUESTION}, {'session_id': ['required']}),
        ]
        with self.fake_ask():
            for body, codes in cases:
                with self.subTest(body=body):
                    response = self.client.post(self.url('questions'), body, format='json')
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.data['codes'], codes)
        self.assertEqual(self.calls, [])

    def test_daily_capacity_is_a_fixed_translated_reply(self):
        with mock.patch('agents.services.ask', side_effect=DailyLimitReached):
            response = self.post(HTTP_ACCEPT_LANGUAGE='ar')
        self.assertError(response, 429, 'daily_capacity')
        self.assertEqual(response.data['detail'], fixed_reply('daily_capacity', 'ar'))
        self.assertFalse(Question.objects.exists())

    def test_unsaved_question_is_unavailable(self):
        with mock.patch('agents.services.ask', return_value=Interaction(decision='abstain')):
            self.assertError(self.post(), 503, 'unavailable')


class ThrottleTests(QuestionAPITestCase):
    """5 questions per minute per IP; history reads are free; no IP in the cache."""

    def post_times(self, count, **extra):
        with self.fake_ask():
            return [self.post(**extra).status_code for _ in range(count)]

    def test_sixth_question_in_a_minute_is_throttled(self):
        self.assertEqual(self.post_times(5), [201] * 5)
        with self.fake_ask():
            self.assertError(self.post(), 429, 'throttled')

    def test_reading_history_is_not_throttled(self):
        self.post_times(5)
        for _ in range(10):
            self.assertEqual(self.client.get(self.url('questions'), {'session_id': SESSION}).status_code, 200)

    def test_each_ip_has_its_own_quota(self):
        self.post_times(5, REMOTE_ADDR='10.0.0.1')
        self.assertEqual(self.post_times(1, REMOTE_ADDR='10.0.0.2'), [201])

    def test_forwarded_for_is_ignored_without_proxies(self):
        for n in range(5):
            self.post_times(1, HTTP_X_FORWARDED_FOR=f'10.1.0.{n}')
        self.assertEqual(self.post_times(1, HTTP_X_FORWARDED_FOR='10.1.0.99'), [429])

    def test_forwarded_for_is_used_behind_one_proxy(self):
        with override_settings(REST_FRAMEWORK={**settings.REST_FRAMEWORK, 'NUM_PROXIES': 1}):
            self.post_times(5, HTTP_X_FORWARDED_FOR='10.2.0.1')
            self.assertEqual(self.post_times(1, HTTP_X_FORWARDED_FOR='10.2.0.2'), [201])

    def test_the_cache_holds_no_ip_address(self):
        self.post_times(1, REMOTE_ADDR='10.9.8.7')
        with connection.cursor() as cursor:
            cursor.execute('SELECT cache_key FROM django_cache')
            keys = [row[0] for row in cursor.fetchall()]
        self.assertTrue(keys)
        self.assertFalse([key for key in keys if '10.9.8.7' in key])


class HistoryTests(QuestionAPITestCase):
    """GET /questions/?session_id= and GET /questions/<uuid>/."""

    def test_lists_the_session_newest_first(self):
        first, second = self.saved(text='الأول'), self.saved(text='الثاني')
        self.saved(session_id='another-session')
        response = self.client.get(self.url('questions'), {'session_id': SESSION})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual([q['uuid'] for q in response.data['results']],
                         [str(second.question.uuid), str(first.question.uuid)])

    def test_sources_of_a_page_are_loaded_in_one_query(self):
        for _ in range(5):
            self.saved()
        # count, page of questions with their interactions, sources
        with self.assertNumQueries(3):
            self.client.get(self.url('questions'), {'session_id': SESSION})

    def test_session_id_is_required_and_checked(self):
        self.assertError(self.client.get(self.url('questions')), 400, 'session_required')
        response = self.client.get(self.url('questions'), {'session_id': 'short'})
        self.assertEqual(response.data['codes'], {'session_id': ['invalid']})

    def test_detail_by_uuid(self):
        interaction = self.saved(decision='refer', sentences=[])
        response = self.client.get(self.url('question', interaction.question.uuid))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['follow_up_number'], str(interaction.question.uuid))

    def test_unknown_uuid_is_404(self):
        self.assertError(self.client.get(self.url('question', uuid.uuid4())), 404, 'not_found')

    def test_no_put_patch_or_delete(self):
        url = self.url('question', self.saved().question.uuid)
        for method in (self.client.put, self.client.patch, self.client.delete):
            self.assertEqual(method(url, {}).status_code, 405)
