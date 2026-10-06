"""Tests for centers/<slug>/questions/: the center's queue, one question, and answering."""

from django.utils import timezone

from api.tests.base import APITestCase
from core.models import Center
from core.tests.support import make_center, make_interaction, make_membership, make_question, make_referral, make_user
from qa.models import AnswerRevision, Referral
from qa.services import revise


class CenterQuestionsTests(APITestCase):
    """Members see their center's questions sent to it, answer and revise; others get 404."""

    def setUp(self):
        super().setUp()
        self.center = make_center(slug='dar')
        self.specialist = make_membership(center=self.center, user=make_user(full_name='Amina')).user
        self.waiting = self.ticket('Waiting question?')
        self.answered = self.ticket('Answered question?')
        revise(self.answered.question, self.specialist, 'First answer.', AnswerRevision.Reason.SPECIALIST_ANSWER)

    def ticket(self, text):
        question = make_interaction(question=make_question(center=self.center, text=text), decision='refer').question
        return make_referral(question=question)

    def list(self, **params):
        return self.client.get(self.url('center-questions', 'dar'), params)

    def test_queue_by_status(self):
        self.authenticate(self.specialist)
        self.assertEqual([q['text'] for q in self.list().data['results']], ['Waiting question?'])
        self.assertEqual([q['text'] for q in self.list(status='answered').data['results']], ['Answered question?'])
        self.assertEqual(self.list(status='all').data['count'], 2)
        self.assertEqual(self.list(status='soon').data['codes']['status'], ['invalid_choice'])
        item = self.list().data['results'][0]
        self.assertEqual((item['ticket']['status'], item['answered_by']), ('open', 'ai'))

    def test_detail_shows_the_ai_answer_and_the_revisions(self):
        self.authenticate(self.specialist)
        data = self.client.get(self.url('center-question', 'dar', self.answered.question.uuid)).data
        self.assertEqual((data['current_answer'], data['answered_by'], data['decision']),
                         ('First answer.', 'center', 'refer'))
        self.assertEqual(data['revisions'][0]['author'], 'Amina')
        self.assertNotIn('asker', data)

    def test_answer_then_revise(self):
        self.authenticate(self.specialist)
        url = self.url('center-question-answer', 'dar', self.waiting.question.uuid)
        response = self.client.post(url, {'text': 'The answer.', 'note': 'Checked.'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual((response.data['current_answer'], response.data['ticket']['status']), ('The answer.', 'answered'))
        self.assertEqual(response.data['revisions'][0]['reason'], 'specialist_answer')
        response = self.client.post(url, {'text': 'The corrected answer.'}, format='json')
        self.assertEqual(response.data['revisions'][0]['reason'], 'correction')
        self.assertEqual(len(response.data['revisions']), 2)

    def test_answer_validation(self):
        self.authenticate(self.specialist)
        response = self.client.post(self.url('center-question-answer', 'dar', self.waiting.question.uuid),
                                    {'text': ''}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_other_centers_and_non_members(self):
        other = self.ticket('Other?')
        other.question.center = make_center()
        other.question.save(update_fields=['center', 'updated_at'])
        self.authenticate(self.specialist)
        self.assertError(self.client.get(self.url('center-question', 'dar', other.question.uuid)), 404, 'not_found')
        self.authenticate()
        self.assertError(self.list(), 404, 'not_found')

    def test_non_operational_center(self):
        Center.objects.filter(pk=self.center.pk).update(is_active=False, updated_at=timezone.now())
        self.authenticate(self.specialist)
        self.assertError(self.list(), 403, 'center_not_operational')
