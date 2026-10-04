"""Tests for ``core.services.memberships``: adding, changing and offboarding."""

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from core.models import Membership
from core.services import memberships
from core.tests.support import make_center, make_membership, make_user

ADMIN = Membership.Role.CENTER_ADMIN
SPECIALIST = Membership.Role.SPECIALIST


class AddMemberTests(TestCase):
    """``add_member`` by email."""

    def setUp(self):
        self.center = make_center()

    def assertCode(self, code, call, *args):
        with self.assertRaises(ValidationError) as caught:
            call(*args)
        self.assertEqual(caught.exception.code, code)

    def test_adds_an_active_member(self):
        user = make_user(email='amina@example.com')
        membership = memberships.add_member(self.center, 'amina@example.com', SPECIALIST)
        self.assertEqual((membership.user, membership.center, membership.role), (user, self.center, SPECIALIST))
        self.assertTrue(membership.is_active)

    def test_email_is_matched_case_insensitively(self):
        user = make_user(email='amina@example.com')
        self.assertEqual(memberships.add_member(self.center, ' AMINA@Example.com ', ADMIN).user, user)

    def test_first_member_of_a_center_may_be_a_specialist(self):
        make_user(email='amina@example.com')
        self.assertEqual(memberships.add_member(self.center, 'amina@example.com', SPECIALIST).role, SPECIALIST)

    def test_unknown_user(self):
        self.assertCode('user_not_found', memberships.add_member, self.center, 'nobody@example.com', SPECIALIST)

    def test_inactive_user(self):
        make_user(email='gone@example.com', is_active=False)
        self.assertCode('user_inactive', memberships.add_member, self.center, 'gone@example.com', SPECIALIST)

    def test_invalid_role(self):
        make_user(email='amina@example.com')
        self.assertCode('invalid_role', memberships.add_member, self.center, 'amina@example.com', 'owner')

    def test_already_member(self):
        membership = make_membership(center=self.center)
        self.assertCode('already_member', memberships.add_member, self.center, membership.user.email, ADMIN)

    def test_former_member_can_rejoin(self):
        former = make_membership(center=self.center, is_active=False, left_at=timezone.now())
        membership = memberships.add_member(self.center, former.user.email, SPECIALIST)
        self.assertNotEqual(membership.pk, former.pk)
        self.assertEqual(Membership.objects.filter(user=former.user).count(), 2)


class ChangeRoleTests(TestCase):
    """``change_role`` keeps at least one active admin."""

    def setUp(self):
        self.center = make_center()
        self.admin = make_membership(center=self.center, role=ADMIN)

    def test_promotes_a_specialist(self):
        specialist = make_membership(center=self.center)
        self.assertEqual(memberships.change_role(specialist, ADMIN).role, ADMIN)
        specialist.refresh_from_db()
        self.assertEqual(specialist.role, ADMIN)

    def test_demotes_an_admin_when_another_remains(self):
        make_membership(center=self.center, role=ADMIN)
        memberships.change_role(self.admin, SPECIALIST)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, SPECIALIST)

    def test_refuses_to_demote_the_last_admin(self):
        with self.assertRaises(ValidationError) as caught:
            memberships.change_role(self.admin, SPECIALIST)
        self.assertEqual(caught.exception.code, 'last_center_admin')
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, ADMIN)

    def test_admins_of_other_centers_do_not_count(self):
        make_membership(role=ADMIN)
        with self.assertRaises(ValidationError) as caught:
            memberships.change_role(self.admin, SPECIALIST)
        self.assertEqual(caught.exception.code, 'last_center_admin')

    def test_inactive_admins_do_not_count(self):
        make_membership(center=self.center, role=ADMIN, is_active=False, left_at=timezone.now())
        with self.assertRaises(ValidationError) as caught:
            memberships.change_role(self.admin, SPECIALIST)
        self.assertEqual(caught.exception.code, 'last_center_admin')

    def test_same_role_is_a_no_op(self):
        updated_at = self.admin.updated_at
        memberships.change_role(self.admin, ADMIN)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.updated_at, updated_at)

    def test_invalid_role(self):
        with self.assertRaises(ValidationError) as caught:
            memberships.change_role(self.admin, 'owner')
        self.assertEqual(caught.exception.code, 'invalid_role')

    def test_ended_membership(self):
        former = make_membership(center=self.center, is_active=False, left_at=timezone.now())
        with self.assertRaises(ValidationError) as caught:
            memberships.change_role(former, ADMIN)
        self.assertEqual(caught.exception.code, 'membership_inactive')


class OffboardTests(TestCase):
    """``offboard`` deactivates instead of deleting, and keeps one admin."""

    def setUp(self):
        self.center = make_center()
        self.admin = make_membership(center=self.center, role=ADMIN)

    def test_deactivates_and_sets_left_at(self):
        specialist = make_membership(center=self.center)
        before = timezone.now()
        memberships.offboard(specialist)
        specialist.refresh_from_db()
        self.assertFalse(specialist.is_active)
        self.assertGreaterEqual(specialist.left_at, before)
        self.assertGreaterEqual(specialist.updated_at, before)

    def test_does_not_delete(self):
        specialist = make_membership(center=self.center)
        memberships.offboard(specialist)
        self.assertTrue(Membership.objects.filter(pk=specialist.pk).exists())

    def test_offboards_an_admin_when_another_remains(self):
        make_membership(center=self.center, role=ADMIN)
        memberships.offboard(self.admin)
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_active)

    def test_refuses_to_offboard_the_last_admin(self):
        with self.assertRaises(ValidationError) as caught:
            memberships.offboard(self.admin)
        self.assertEqual(caught.exception.code, 'last_center_admin')
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_already_ended(self):
        specialist = make_membership(center=self.center)
        memberships.offboard(specialist)
        with self.assertRaises(ValidationError) as caught:
            memberships.offboard(specialist)
        self.assertEqual(caught.exception.code, 'membership_inactive')
