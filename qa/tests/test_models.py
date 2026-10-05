"""Tests for qa/models.py: public identifier, session history, the daily count and referrals."""

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from core.tests.support import make_center, make_referral, make_user
from qa.models import Question, Referral


class QuestionTests(TestCase):
    """``Question`` identifiers and ``QuestionQuerySet``."""

    def setUp(self):
        self.center = make_center(is_default=True)

    def ask(self, session_id='session-1', text='سؤال'):
        return Question.objects.create(center=self.center, text=text, session_id=session_id)

    def test_each_question_gets_its_own_uuid(self):
        first, second = self.ask(), self.ask()
        self.assertIsNotNone(first.uuid)
        self.assertNotEqual(first.uuid, second.uuid)

    def test_for_session_returns_that_session_newest_first(self):
        older, newer = self.ask(text='1'), self.ask(text='2')
        self.ask(session_id='session-2')
        Question.objects.filter(pk=older.pk).update(created_at=timezone.now() - timedelta(minutes=5),
                                                    updated_at=timezone.now())
        self.assertEqual(list(Question.objects.for_session('session-1')), [newer, older])

    def test_asked_today_counts_since_midnight_utc(self):
        today, yesterday = self.ask(), self.ask()
        midnight = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        Question.objects.filter(pk=yesterday.pk).update(created_at=midnight - timedelta(seconds=1),
                                                        updated_at=timezone.now())
        self.assertEqual(list(Question.objects.asked_today()), [today])


class ReferralTests(TestCase):
    """``ReferralQuerySet`` and the date constraints of ``Referral`` (ADR 0021)."""

    def test_pending_and_assigned_to(self):
        waiting = make_referral()
        taken = make_referral(status=Referral.Status.IN_PROGRESS, assigned_to=make_user())
        make_referral(status=Referral.Status.ANSWERED, answered_at=timezone.now())
        make_referral(status=Referral.Status.CLOSED, closed_at=timezone.now())
        self.assertCountEqual(Referral.objects.pending(), [waiting, taken])
        self.assertEqual(list(Referral.objects.assigned_to(taken.assigned_to)), [taken])
        self.assertTrue(waiting.is_pending)

    def test_answered_and_closed_need_their_date(self):
        for status in (Referral.Status.ANSWERED, Referral.Status.CLOSED):
            with self.subTest(status=status), self.assertRaises(IntegrityError), transaction.atomic():
                make_referral(status=status)
