"""Tests for anonymous asking: /api/v1/questions/ (ADR 0017). The flow is replaced by a fake ``ask``."""

import uuid
from unittest import mock

from django.conf import settings
from django.db import connection
from django.test import override_settings
from rest_framework_simplejwt.tokens import RefreshToken

from agents.replies import fixed_reply
from agents.services import DailyLimitReached
from api.tests.base import APITestCase
from core.tests.support import make_center, make_user
from knowledge.services.ingest import ingest
from knowledge.tests.support import FakeEmbedder, make_question
from qa.models import AnswerRevision, Interaction, Question, Referral
from qa.services import open_referral, revise

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
        self.reviser = make_user(is_staff=True, is_superuser=True)
        self.askers = []

    def saved(self, text=QUESTION, session_id=SESSION, lang='ar', decision='answer', level='B',
              sentences=None, dropped=None, answer='الإسلام لم ينتشر بالسيف [Q229].', asker=None, sent=False):
        """Save a question and its interaction as ``agents.services.ask`` would."""
        question = Question.objects.create(center=self.center, text=text, lang=lang, session_id=session_id,
                                           asker=asker)
        if sentences is None:
            sentences = [{'text': 'الإسلام لم ينتشر بالسيف.', 'quote': QUOTE, 'number': 229}]
        interaction = Interaction.objects.create(question=question, decision=decision, level=level,
                                                 answer_text=answer, sentences=sentences, dropped=dropped or [])
        if sent:  # the asker chose to send it to the specialists
            open_referral(question, Referral.Reason.LEVEL_D if level == 'D' else Referral.Reason.NO_EVIDENCE)
        return interaction

    def fake_ask(self, **outcome):
        """A replacement for ``ask`` that records its arguments and saves ``outcome``."""
        def ask(text, session_id='', asker=None):
            self.calls.append((text, session_id))
            self.askers.append(asker)
            return self.saved(text=text, session_id=session_id, asker=asker, **outcome)
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
                                      'answered_by', 'review', 'sentences', 'notes', 'verification',
                                      'follow_up_number', 'can_ask_specialist', 'referral_mode', 'referral_status',
                                      'referral_live_until', 'created_at'])
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
        self.assertEqual((response.data['can_ask_specialist'], response.data['referral_status']), (True, None))
        self.assertIsNone(response.data['follow_up_number'])  # nothing sent before the asker chooses
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
        self.assertEqual(self.askers, [None])
        self.assertEqual(self.client.get(self.url('questions'), {'session_id': SESSION}).status_code, 200)

    def test_anonymous_question_has_no_asker(self):
        with self.fake_ask():
            self.post()
        self.assertEqual(self.askers, [None])
        self.assertIsNone(Question.objects.get().asker)


class AskerTests(QuestionAPITestCase):
    """A valid access token links the question to the account (ADR 0019); anything else stays anonymous."""

    def bearer(self, user):
        """Send a real access token, so OptionalJWTAuthentication itself is exercised."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')

    def test_logged_in_question_is_linked_to_the_account(self):
        user = make_user()
        self.bearer(user)
        with self.fake_ask():
            self.assertEqual(self.post().status_code, 201)
        self.assertEqual(self.askers, [user])
        self.assertEqual(Question.objects.get().asker, user)

    def test_token_of_a_deactivated_account_asks_anonymously(self):
        user = make_user()
        self.bearer(user)
        user.is_active = False
        user.save(update_fields=['is_active', 'updated_at'])
        with self.fake_ask():
            self.assertEqual(self.post().status_code, 201)
        self.assertEqual(self.askers, [None])

    def test_the_answer_does_not_reveal_the_asker(self):
        self.bearer(make_user(email='amina@example.com'))
        with self.fake_ask():
            body = self.post().json()
        self.assertNotIn('asker', body)
        self.assertNotIn('amina@example.com', str(body))


class MyQuestionsTests(QuestionAPITestCase):
    """GET /me/questions/: the caller's own questions, from every session, newest first."""

    def test_requires_login(self):
        self.assertError(self.client.get(self.url('my-questions')), 401, 'not_authenticated')

    def test_lists_only_the_callers_questions_across_sessions(self):
        user = self.authenticate()
        older = self.saved(text='First?', session_id='phone-0001', asker=user)
        newer = self.saved(text='Second?', session_id='laptop-0001', asker=user)
        self.saved(text='Someone else?', asker=make_user())
        self.saved(text='Anonymous?')
        response = self.client.get(self.url('my-questions'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['uuid'] for item in response.json()['results']],
                         [str(newer.question.uuid), str(older.question.uuid)])
        self.assertEqual(response.json()['results'][0]['sentences'][0]['source']['number'], 229)

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
        for index in range(5):
            interaction = self.saved()
            if index % 2:
                revise(interaction.question, self.reviser, 'Revised.', AnswerRevision.Reason.CORRECTION)
        # count, page with interactions and centers, revisions of the page, sources
        with self.assertNumQueries(4):
            self.client.get(self.url('questions'), {'session_id': SESSION})

    def test_session_id_is_required_and_checked(self):
        self.assertError(self.client.get(self.url('questions')), 400, 'session_required')
        response = self.client.get(self.url('questions'), {'session_id': 'short'})
        self.assertEqual(response.data['codes'], {'session_id': ['invalid']})

    def test_detail_by_uuid(self):
        interaction = self.saved(decision='refer', sentences=[], sent=True)
        response = self.client.get(self.url('question', interaction.question.uuid))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['follow_up_number'], str(interaction.question.uuid))

    def test_unknown_uuid_is_404(self):
        self.assertError(self.client.get(self.url('question', uuid.uuid4())), 404, 'not_found')

    def test_no_put_patch_or_delete(self):
        url = self.url('question', self.saved().question.uuid)
        for method in (self.client.put, self.client.patch, self.client.delete):
            self.assertEqual(method(url, {}).status_code, 405)


class RevisionPayloadTests(QuestionAPITestCase):
    """A revised answer replaces the AI's for the asker, signed with the center's name (ADR 0020)."""

    def test_unrevised_answer_comes_from_the_ai(self):
        question = self.saved().question
        body = self.client.get(self.url('question', question.uuid)).json()
        self.assertEqual((body['answered_by'], body['review']), ('ai', None))
        self.assertEqual(len(body['sentences']), 1)

    def test_latest_revision_replaces_the_answer_sentences_and_notes(self):
        question = self.saved(level='C').question
        revise(question, self.reviser, 'First correction.', AnswerRevision.Reason.CORRECTION)
        latest = revise(question, self.reviser, 'Second correction.', AnswerRevision.Reason.CLARIFICATION,
                        note='Internal only')
        body = self.client.get(self.url('question', question.uuid)).json()
        self.assertEqual(body['answer'], 'Second correction.')
        self.assertEqual(body['answered_by'], 'center')
        self.assertEqual(body['review']['center'], self.center.name)
        self.assertEqual(body['review']['revised_at'], latest.created_at.isoformat().replace('+00:00', 'Z'))
        self.assertEqual((body['sentences'], body['notes']), ([], []))
        self.assertNotIn('Internal only', str(body))
        self.assertNotIn(self.reviser.email, str(body))

    def test_history_and_my_questions_show_the_revision(self):
        user = self.authenticate()
        question = self.saved(asker=user).question
        revise(question, self.reviser, 'Answered by the center.', AnswerRevision.Reason.SPECIALIST_ANSWER)
        for response in (self.client.get(self.url('questions'), {'session_id': SESSION}),
                         self.client.get(self.url('my-questions'))):
            self.assertEqual(response.json()['results'][0]['answer'], 'Answered by the center.')


class ReferralStatusTests(QuestionAPITestCase):
    """The asker follows a referred question through ``referral_status`` (ADR 0021)."""

    def status_of(self, question):
        return self.client.get(self.url('question', question.uuid)).json()['referral_status']

    def test_a_question_not_referred_has_no_status(self):
        self.assertIsNone(self.status_of(self.saved().question))

    def test_status_follows_the_ticket_until_answered(self):
        question = self.saved(decision='refer', level='D', sentences=[], answer=fixed_reply('refer', 'ar'),
                              sent=True).question
        self.assertEqual(self.status_of(question), 'open')
        revise(question, self.reviser, 'Answered by the center.', AnswerRevision.Reason.SPECIALIST_ANSWER)
        self.assertEqual(self.status_of(question), 'answered')

    def test_history_with_referrals_keeps_its_query_count(self):
        for decision in ('answer', 'refer', 'refer'):
            self.saved(decision=decision, sent=decision == 'refer')
        # count, page with interactions, centers and referrals, revisions of the page, sources
        with self.assertNumQueries(4):
            response = self.client.get(self.url('questions'), {'session_id': SESSION})
        self.assertEqual([q['referral_status'] for q in response.json()['results']], ['open', 'open', None])


class SpecialistRequestTests(QuestionAPITestCase):
    """The asker sends a question the AI did not answer to the specialists: live or as a ticket."""

    def request(self, question, mode='live', session_id=SESSION):
        return self.client.post(self.url('question-specialist', question.uuid),
                                {'mode': mode, 'session_id': session_id}, format='json')

    def test_live_request_opens_a_live_referral(self):
        question = self.saved(decision='refer', level='D', sentences=[]).question
        response = self.request(question)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual((response.data['referral_mode'], response.data['referral_status'],
                          response.data['can_ask_specialist']), ('live', 'open', False))
        self.assertIsNotNone(response.data['referral_live_until'])
        self.assertEqual(response.data['follow_up_number'], str(question.uuid))

    def test_ticket_has_no_live_window_and_abstentions_qualify(self):
        question = self.saved(decision='abstain', level='B', sentences=[]).question
        response = self.request(question, mode='ticket')
        self.assertEqual((response.data['referral_mode'], response.data['referral_live_until']), ('ticket', None))
        self.assertEqual(Referral.objects.get().reason, Referral.Reason.NO_EVIDENCE)

    def test_only_the_asker(self):
        question = self.saved(decision='refer', sentences=[]).question
        self.assertError(self.request(question, session_id='another-session'), 404, 'not_found')
        mine = self.saved(decision='refer', sentences=[], asker=make_user()).question
        self.assertError(self.request(mine), 404, 'not_found')
        self.authenticate(mine.asker)
        self.assertEqual(self.request(mine, session_id='').status_code, 201)

    def test_refusals(self):
        answered = self.saved().question
        self.assertError(self.request(answered), 400, 'not_referable')
        question = self.saved(decision='refer', sentences=[]).question
        self.request(question)
        self.assertError(self.request(question), 400, 'referral_exists')
        response = self.request(self.saved(decision='refer', sentences=[]).question, mode='soon')
        self.assertEqual(response.data['codes']['mode'], ['invalid_choice'])

    def test_logging_in_then_saving_a_ticket_claims_the_anonymous_question(self):
        question = self.saved(decision='refer', sentences=[]).question
        user = self.authenticate()
        self.assertEqual(self.request(question, mode='ticket').status_code, 201)
        question.refresh_from_db()
        self.assertEqual(question.asker, user)
        self.assertEqual([q['uuid'] for q in self.client.get(self.url('my-questions')).data['results']],
                         [str(question.uuid)])

