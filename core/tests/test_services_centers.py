"""Tests for ``core.services.centers``: registration and review of centers."""

from django.core.exceptions import ValidationError
from django.test import TestCase

from core.models import Center, Membership
from core.services import centers
from core.tests.support import make_center, make_user


class RegisterCenterTests(TestCase):
    """A registered center is pending and its applicant is its center admin."""

    def test_creates_pending_center_with_applicant_as_admin(self):
        applicant = make_user()
        center = centers.register_center(applicant, name='Dar al-Ifta', country='MA')
        self.assertEqual(center.status, Center.Status.PENDING)
        self.assertEqual(center.slug, 'dar-al-ifta')
        membership = Membership.objects.get(center=center)
        self.assertEqual((membership.user, membership.role), (applicant, Membership.Role.CENTER_ADMIN))

    def test_ignores_status_and_default_from_the_caller(self):
        center = centers.register_center(make_user(), name='A', status='approved', is_default=True)
        self.assertEqual(center.status, Center.Status.PENDING)
        self.assertFalse(center.is_default)

    def test_slug_is_unique_and_has_a_fallback_for_arabic_names(self):
        make_center(slug='center')
        self.assertEqual(centers.unique_slug('دار الإفتاء'), 'center-2')
        make_center(slug='dar')
        self.assertEqual(centers.unique_slug('Dar'), 'dar-2')


class ReviewTests(TestCase):
    """Only pending centers are reviewed; rejection needs a reason."""

    def setUp(self):
        self.reviewer = make_user(is_staff=True)
        self.center = make_center(status=Center.Status.PENDING)

    def assertCode(self, code, call, *args):
        with self.assertRaises(ValidationError) as caught:
            call(*args)
        self.assertEqual(caught.exception.code, code)

    def test_approve(self):
        centers.approve(self.center, self.reviewer)
        self.assertEqual(self.center.status, Center.Status.APPROVED)
        self.assertEqual(self.center.reviewed_by, self.reviewer)
        self.assertIsNotNone(self.center.reviewed_at)
        self.assertTrue(self.center.is_operational)

    def test_reject_records_the_reason(self):
        centers.reject(self.center, self.reviewer, '  Missing documents.  ')
        self.assertEqual(self.center.status, Center.Status.REJECTED)
        self.assertEqual(self.center.rejection_reason, 'Missing documents.')

    def test_reject_requires_a_reason(self):
        for reason in ('', '   ', None):
            with self.subTest(reason=reason):
                self.assertCode('rejection_reason_required', centers.reject, self.center, self.reviewer, reason)

    def test_only_pending_centers_are_reviewed(self):
        centers.approve(self.center, self.reviewer)
        self.assertCode('center_not_pending', centers.approve, self.center, self.reviewer)
        self.assertCode('center_not_pending', centers.reject, self.center, self.reviewer, 'Late.')

    def test_reviewer_deletion_keeps_the_review(self):
        centers.approve(self.center, self.reviewer)
        self.reviewer.delete()
        self.center.refresh_from_db()
        self.assertIsNone(self.center.reviewed_by)
        self.assertEqual(self.center.status, Center.Status.APPROVED)
