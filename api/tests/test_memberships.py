"""Tests for centers/<slug>/memberships/ and its detail and offboard endpoints."""

import uuid

from api.tests.base import APITestCase
from core.models import Center, Membership
from core.tests.support import make_center, make_membership, make_user

ADMIN = Membership.Role.CENTER_ADMIN
SPECIALIST = Membership.Role.SPECIALIST


class MembershipEndpointTests(APITestCase):
    """Center admins of operational centers manage memberships through the services."""

    def setUp(self):
        super().setUp()
        self.center = make_center(slug='dar')
        self.admin_membership = make_membership(center=self.center, role=ADMIN)
        self.specialist = make_membership(center=self.center)
        self.authenticate(self.admin_membership.user)

    def test_list(self):
        response = self.client.get(self.url('memberships', 'dar'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(set(response.data['results'][0]), {'uuid', 'user', 'role', 'is_active', 'created_at', 'left_at'})

    def test_add_by_email(self):
        make_user(email='new@example.com')
        response = self.client.post(self.url('memberships', 'dar'), {'email': 'NEW@example.com', 'role': SPECIALIST})
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['user']['email'], 'new@example.com')

    def test_add_reports_service_codes(self):
        cases = (
            ('nobody@example.com', 'user_not_found'),
            (self.specialist.user.email, 'already_member'),
        )
        for email, code in cases:
            with self.subTest(code=code):
                response = self.client.post(self.url('memberships', 'dar'), {'email': email, 'role': SPECIALIST})
                self.assertError(response, 400, code)

    def test_change_role(self):
        url = self.url('membership', 'dar', self.specialist.uuid)
        response = self.client.patch(url, {'role': ADMIN})
        self.assertEqual((response.status_code, response.data['role']), (200, ADMIN))

    def test_demoting_the_last_admin_is_refused(self):
        response = self.client.patch(self.url('membership', 'dar', self.admin_membership.uuid), {'role': SPECIALIST})
        self.assertError(response, 400, 'last_center_admin')

    def test_offboard(self):
        response = self.client.post(self.url('membership-offboard', 'dar', self.specialist.uuid))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['is_active'])
        self.assertIsNotNone(response.data['left_at'])

    def test_offboarding_twice_is_refused(self):
        url = self.url('membership-offboard', 'dar', self.specialist.uuid)
        self.client.post(url)
        self.assertError(self.client.post(url), 400, 'membership_inactive')

    def test_no_delete(self):
        self.assertError(self.client.delete(self.url('membership', 'dar', self.specialist.uuid)), 405,
                         'method_not_allowed')

    def test_membership_of_another_center_is_404(self):
        other = make_membership()
        self.assertError(self.client.get(self.url('membership', 'dar', other.uuid)), 404, 'not_found')
        self.assertError(self.client.get(self.url('membership', 'dar', uuid.uuid4())), 404, 'not_found')

    def test_permissions(self):
        urls = [self.url('memberships', 'dar'), self.url('membership', 'dar', self.specialist.uuid)]
        self.authenticate(self.specialist.user)
        for url in urls:
            with self.subTest(url=url, caller='specialist'):
                self.assertError(self.client.get(url), 403, 'not_center_admin')
        self.authenticate(make_user())
        for url in urls:
            with self.subTest(url=url, caller='non-member'):
                self.assertError(self.client.get(url), 404, 'not_found')
        self.client.force_authenticate(None)
        for url in urls:
            with self.subTest(url=url, caller='anonymous'):
                self.assertError(self.client.get(url), 401, 'not_authenticated')

    def test_pending_center_is_blocked(self):
        Center.objects.filter(pk=self.center.pk).update(status=Center.Status.PENDING)
        self.assertError(self.client.get(self.url('memberships', 'dar')), 403, 'center_not_operational')
