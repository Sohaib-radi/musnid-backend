"""Tests for qa/services.py: who may revise an answer, and what a revision saves (ADR 0020)."""

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from core.models import Center, Membership
from core.tests.support import make_center, make_interaction, make_membership, make_question, make_user
from qa.models import AnswerRevision
from qa.services import TEXT_MAX, can_revise, revise


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
