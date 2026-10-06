"""Tests for qa/services.py: revising answers (ADR 0020) and handling referrals (ADR 0021)."""

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from core.models import Center, Membership
from core.tests.support import (
    make_center, make_interaction, make_membership, make_question, make_referral, make_user,
)
from qa.models import AnswerRevision, HumanLabel, Referral
from qa.services import TEXT_MAX, assign, can_revise, close, label, open_referral, revise


class CanReviseTests(TestCase):
    """Staff with the permission, and active members of an operational center."""

    def setUp(self):
        self.center = make_center()
        self.question = make_question(center=self.center)

    def test_superuser(self):
        self.assertTrue(can_revise(make_user(is_staff=True, is_superuser=True), self.question))

    def test_staff_needs_the_add_permission(self):
        staff = make_user(is_staff=True)
        self.assertFalse(can_revise(staff, self.question))
        staff.user_permissions.add(Permission.objects.get(codename='add_answerrevision'))
        staff = type(staff).objects.get(pk=staff.pk)  # reload: permissions are cached per instance
        self.assertTrue(can_revise(staff, self.question))

    def test_active_members_of_the_center(self):
        for role in Membership.Role.values:
            with self.subTest(role=role):
                member = make_membership(center=self.center, role=role).user
                self.assertTrue(can_revise(member, self.question))

    def test_members_of_another_center_are_refused(self):
        outsider = make_membership(center=make_center()).user
        self.assertFalse(can_revise(outsider, self.question))

    def test_former_members_are_refused(self):
        membership = make_membership(center=self.center)
        membership.is_active, membership.left_at = False, timezone.now()  # constraint: both or neither
        membership.save(update_fields=['is_active', 'left_at', 'updated_at'])
        self.assertFalse(can_revise(membership.user, self.question))

    def test_members_of_a_center_not_operational_are_refused(self):
        pending = make_center(status=Center.Status.PENDING)
        member = make_membership(center=pending).user
        self.assertFalse(can_revise(member, make_question(center=pending)))

    def test_deactivated_users_are_refused(self):
        self.assertFalse(can_revise(make_user(is_staff=True, is_superuser=True, is_active=False), self.question))


class ReviseTests(TestCase):
    """``revise`` checks its input and adds a revision, leaving the AI answer untouched."""

    def setUp(self):
        self.interaction = make_interaction(answer_text='AI answer [Q1].')
        self.question = self.interaction.question
        self.member = make_membership(center=self.question.center).user

    def assertRefused(self, code, **arguments):
        values = {'author': self.member, 'text': 'A text.', 'reason': AnswerRevision.Reason.CORRECTION, **arguments}
        with self.assertRaises(ValidationError) as caught:
            revise(self.question, **values)
        self.assertEqual(caught.exception.code, code)
        self.assertFalse(AnswerRevision.objects.exists())

    def test_saves_a_revision_and_keeps_the_ai_answer(self):
        revision = revise(self.question, self.member, '  The corrected answer.  ', AnswerRevision.Reason.CORRECTION,
                          note=' Typo in the date. ')
        self.assertEqual((revision.text, revision.note, revision.author), ('The corrected answer.', 'Typo in the date.',
                                                                         self.member))
        self.interaction.refresh_from_db()
        self.assertEqual(self.interaction.answer_text, 'AI answer [Q1].')

    def test_latest_revision_is_the_newest(self):
        self.assertIsNone(self.question.latest_revision())
        revise(self.question, self.member, 'First.', AnswerRevision.Reason.CORRECTION)
        second = revise(self.question, self.member, 'Second.', AnswerRevision.Reason.CLARIFICATION)
        self.assertEqual(type(self.question).objects.get(pk=self.question.pk).latest_revision(), second)

    def test_refusals(self):
        self.assertRefused('revision_not_allowed', author=make_user())
        self.assertRefused('revision_text_required', text='   ')
        self.assertRefused('revision_text_too_long', text='x' * (TEXT_MAX + 1))
        self.assertRefused('revision_reason_invalid', reason='because')


class ReferralServiceTests(TestCase):
    """``open_referral``, ``assign``, ``close``, and ``revise`` marking a referral answered (ADR 0021)."""

    def setUp(self):
        self.referral = make_referral()
        self.center = self.referral.center
        self.specialist = make_membership(center=self.center).user

    def assertRefused(self, code, call):
        with self.assertRaises(ValidationError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def test_open_referral_belongs_to_the_question_center(self):
        question = make_interaction(decision='refer').question
        referral = open_referral(question, Referral.Reason.LEVEL_D)
        self.assertEqual((referral.center, referral.status, referral.reason),
                         (question.center, Referral.Status.OPEN, Referral.Reason.LEVEL_D))

    def test_a_specialist_takes_a_referral(self):
        referral = assign(self.referral, self.specialist, self.specialist)
        self.referral.refresh_from_db()
        self.assertEqual((self.referral.status, self.referral.assigned_to),
                         (Referral.Status.IN_PROGRESS, self.specialist))
        self.assertEqual(referral.pk, self.referral.pk)

    def test_reassigning_a_referral_in_progress(self):
        colleague = make_membership(center=self.center).user
        assign(self.referral, self.specialist, self.specialist)
        assign(self.referral, self.specialist, colleague)
        self.referral.refresh_from_db()
        self.assertEqual(self.referral.assigned_to, colleague)

    def test_assign_refusals(self):
        outsider = make_membership().user
        former = make_membership(center=self.center).user
        now = timezone.now()
        Membership.objects.filter(user=former).update(is_active=False, left_at=now, updated_at=now)
        self.assertRefused('referral_not_allowed', lambda: assign(self.referral, outsider, outsider))
        self.assertRefused('referral_assignee_invalid', lambda: assign(self.referral, self.specialist, outsider))
        self.assertRefused('referral_assignee_invalid', lambda: assign(self.referral, self.specialist, former))
        self.referral.refresh_from_db()
        self.assertEqual(self.referral.status, Referral.Status.OPEN)

    def test_close_keeps_the_note_and_the_date(self):
        close(self.referral, self.specialist, '  Duplicate of an earlier question.  ')
        self.referral.refresh_from_db()
        self.assertEqual((self.referral.status, self.referral.close_note),
                         (Referral.Status.CLOSED, 'Duplicate of an earlier question.'))
        self.assertIsNotNone(self.referral.closed_at)

    def test_close_refusals(self):
        self.assertRefused('referral_not_allowed', lambda: close(self.referral, make_user(), 'Why.'))
        self.assertRefused('referral_note_required', lambda: close(self.referral, self.specialist, '  '))

    def test_answered_or_closed_referrals_cannot_be_assigned_or_closed(self):
        close(self.referral, self.specialist, 'Duplicate.')
        self.assertRefused('referral_not_pending', lambda: assign(self.referral, self.specialist, self.specialist))
        self.assertRefused('referral_not_pending', lambda: close(self.referral, self.specialist, 'Again.'))

    def test_revise_marks_the_referral_answered(self):
        revise(self.referral.question, self.specialist, 'The answer.', AnswerRevision.Reason.SPECIALIST_ANSWER)
        self.referral.refresh_from_db()
        self.assertEqual(self.referral.status, Referral.Status.ANSWERED)
        answered_at = self.referral.answered_at
        self.assertIsNotNone(answered_at)
        revise(self.referral.question, self.specialist, 'Clarified.', AnswerRevision.Reason.CLARIFICATION)
        self.referral.refresh_from_db()
        self.assertEqual(self.referral.answered_at, answered_at)

    def test_answering_a_closed_referral_marks_it_answered(self):
        close(self.referral, self.specialist, 'Duplicate.')
        revise(self.referral.question, self.specialist, 'Answered anyway.', AnswerRevision.Reason.SPECIALIST_ANSWER)
        self.referral.refresh_from_db()
        self.assertEqual(self.referral.status, Referral.Status.ANSWERED)

    def test_revising_a_question_without_referral_opens_none(self):
        question = make_interaction().question
        revise(question, make_user(is_staff=True, is_superuser=True), 'Corrected.', AnswerRevision.Reason.CORRECTION)
        self.assertFalse(Referral.objects.filter(question=question).exists())


class LabelTests(TestCase):
    """``label``: a reviewer's verdict on the AI answer, one per reviewer, never shown to the asker."""

    def setUp(self):
        self.interaction = make_interaction(answer_text='AI answer [Q1].')
        self.reviewer = make_membership(center=self.interaction.question.center).user

    def assertRefused(self, code, **arguments):
        values = {'verdict': HumanLabel.Verdict.APPROVE, **arguments}
        with self.assertRaises(ValidationError) as caught:
            label(self.interaction, arguments.pop('reviewer', self.reviewer), **{
                key: value for key, value in values.items() if key != 'reviewer'})
        self.assertEqual(caught.exception.code, code)

    def test_a_new_verdict_replaces_the_reviewers_previous_one(self):
        label(self.interaction, self.reviewer, HumanLabel.Verdict.APPROVE)
        changed = label(self.interaction, self.reviewer, HumanLabel.Verdict.CORRECT,
                        corrected_answer=' Better answer. ')
        self.assertEqual(HumanLabel.objects.count(), 1)
        self.assertEqual((changed.verdict, changed.corrected_answer), ('correct', 'Better answer.'))
        self.assertFalse(AnswerRevision.objects.exists())  # the asker's answer is untouched

    def test_only_a_correction_keeps_an_answer(self):
        saved = label(self.interaction, self.reviewer, HumanLabel.Verdict.REJECT, reason='Invented source.',
                      corrected_answer='ignored')
        self.assertEqual(saved.corrected_answer, '')

    def test_refusals(self):
        self.assertRefused('label_not_allowed', reviewer=make_user())
        self.assertRefused('label_verdict_invalid', verdict='maybe')
        self.assertRefused('label_correction_required', verdict=HumanLabel.Verdict.CORRECT)
        self.assertRefused('label_reason_required', verdict=HumanLabel.Verdict.REJECT)


class AnswerTranslationTests(TestCase):
    """A specialist's answer in another language than the question's is translated for the asker."""

    def setUp(self):
        self.question = make_interaction(question=make_question(text='Do I have to pay zakat on savings?',
                                                                lang='en')).question
        self.specialist = make_membership(center=self.question.center, user=make_user(preferred_lang='ar')).user

    def test_arabic_answer_to_an_english_question_is_translated(self):
        from unittest import mock
        with mock.patch('agents.translation.translate', return_value='Yes, zakat is due.') as translate:
            revision = revise(self.question, self.specialist, 'نعم، تجب الزكاة.', AnswerRevision.Reason.SPECIALIST_ANSWER)
        translate.assert_called_once_with('نعم، تجب الزكاة.', 'en')
        self.assertEqual((revision.lang, revision.text, revision.translated_text, revision.shown_text),
                         ('ar', 'نعم، تجب الزكاة.', 'Yes, zakat is due.', 'Yes, zakat is due.'))

    def test_same_language_is_not_translated_and_a_failure_keeps_the_original(self):
        from unittest import mock
        with mock.patch('agents.translation.translate') as translate:
            revision = revise(self.question, self.specialist, 'Yes, it is due.', AnswerRevision.Reason.SPECIALIST_ANSWER)
        translate.assert_not_called()
        self.assertEqual((revision.lang, revision.translated_text), ('en', ''))
        with mock.patch('agents.translation.translate', return_value=None):
            failed = revise(self.question, self.specialist, 'نعم.', AnswerRevision.Reason.CORRECTION)
        self.assertEqual(failed.shown_text, 'نعم.')

