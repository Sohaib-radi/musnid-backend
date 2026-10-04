"""Tests for ``core.models.membership``: constraints and querysets."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from core.models import Membership
from core.tests.support import make_center, make_membership, make_user


class MembershipModelTests(TestCase):
    """Defaults, links and string form."""

    def test_defaults(self):
        membership = make_membership()
        self.assertTrue(membership.is_active)
        self.assertIsNone(membership.left_at)
        self.assertIsNotNone(membership.uuid)
        self.assertEqual(membership.role, Membership.Role.SPECIALIST)

    def test_reverse_accessors(self):
        membership = make_membership()
        self.assertEqual(list(membership.user.memberships.all()), [membership])
        self.assertEqual(list(membership.center.core_membership_set.all()), [membership])

    def test_str(self):
        membership = make_membership()
        self.assertEqual(
            str(membership), f'{membership.user.email} – {membership.center.name} (Specialist)',
        )

    def test_deleting_user_or_center_deletes_memberships(self):
        for owner in ('user', 'center'):
            with self.subTest(owner=owner):
                membership = make_membership()
                getattr(membership, owner).delete()
                self.assertFalse(Membership.objects.filter(pk=membership.pk).exists())


class MembershipConstraintTests(TestCase):
    """``unique_active_membership`` and ``membership_active_matches_left_at``."""

    def test_second_active_membership_is_refused(self):
        membership = make_membership()
        with self.assertRaises(IntegrityError) as caught, transaction.atomic():
            make_membership(user=membership.user, center=membership.center)
        self.assertIn('unique_active_membership', str(caught.exception))

    def test_rejoining_after_leaving_is_allowed(self):
        old = make_membership(is_active=False, left_at=timezone.now())
        new = make_membership(user=old.user, center=old.center)
        self.assertTrue(new.is_active)

    def test_same_user_in_two_centers_is_allowed(self):
        user = make_user()
        make_membership(user=user)
        make_membership(user=user)
        self.assertEqual(user.memberships.active().count(), 2)

    def test_active_membership_with_left_at_is_refused(self):
        with self.assertRaises(IntegrityError) as caught, transaction.atomic():
            make_membership(is_active=True, left_at=timezone.now())
        self.assertIn('membership_active_matches_left_at', str(caught.exception))

    def test_inactive_membership_without_left_at_is_refused(self):
        with self.assertRaises(IntegrityError) as caught, transaction.atomic():
            make_membership(is_active=False, left_at=None)
        self.assertIn('membership_active_matches_left_at', str(caught.exception))

    def test_full_clean_reports_constraint_messages(self):
        existing = make_membership()
        duplicate = Membership(
            user=existing.user, center=existing.center, role=Membership.Role.SPECIALIST,
            is_active=True, left_at=timezone.now(),
        )
        with self.assertRaises(ValidationError) as caught:
            duplicate.full_clean()
        messages = caught.exception.messages
        self.assertIn('This user is already an active member of this center.', messages)
        self.assertIn(
            'An active membership cannot have a leaving date, '
            'and an inactive membership must have one.',
            messages,
        )


class MembershipQuerySetTests(TestCase):
    """``active``, ``center_admins``, ``specialists`` and ``for_center``."""

    def setUp(self):
        self.center = make_center()
        self.admin = make_membership(center=self.center, role=Membership.Role.CENTER_ADMIN)
        self.specialist = make_membership(center=self.center)
        self.former = make_membership(
            center=self.center, is_active=False, left_at=timezone.now(),
        )
        self.elsewhere = make_membership()

    def test_active(self):
        self.assertNotIn(self.former, Membership.objects.active())
        self.assertIn(self.specialist, Membership.objects.active())

    def test_center_admins(self):
        self.assertEqual(list(Membership.objects.center_admins()), [self.admin])

    def test_specialists_include_inactive_ones(self):
        self.assertEqual(
            set(Membership.objects.for_center(self.center).specialists()),
            {self.specialist, self.former},
        )

    def test_methods_chain(self):
        self.assertEqual(
            list(Membership.objects.for_center(self.center).active().specialists()),
            [self.specialist],
        )

    def test_for_center(self):
        self.assertNotIn(self.elsewhere, Membership.objects.for_center(self.center))
