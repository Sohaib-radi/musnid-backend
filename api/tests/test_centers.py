"""Tests for centers/<slug>/, dashboard/ and settings/."""

from django.utils import translation

from api.tests.base import APITestCase
from core.models import Center, Membership
from core.tests.support import make_center, make_membership

ADMIN = Membership.Role.CENTER_ADMIN


class CenterAccessMixin:
    """Members of a center with each role, for the center endpoints."""

    def setUp(self):
        super().setUp()
        self.center = make_center(name='Dar al-Ifta', slug='dar')
        self.admin = make_membership(center=self.center, role=ADMIN).user
        self.specialist = make_membership(center=self.center).user


class CenterDetailTests(CenterAccessMixin, APITestCase):
    """Members can read their center, whatever its status."""

    def test_requires_authentication(self):
        self.assertError(self.client.get(self.url('center', 'dar')), 401, 'not_authenticated')

    def test_member_reads_the_center(self):
        self.authenticate(self.specialist)
        response = self.client.get(self.url('center', 'dar'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.data['slug'], response.data['state']), ('dar', 'operational'))
        self.assertNotIn('id', response.data)

    def test_non_member_gets_404(self):
        self.authenticate()
        self.assertError(self.client.get(self.url('center', 'dar')), 404, 'not_found')

    def test_applicant_reads_pending_and_rejected_centers(self):
        for state, status in (('pending_review', Center.Status.PENDING), ('rejected', Center.Status.REJECTED)):
            with self.subTest(status=status):
                Center.objects.filter(pk=self.center.pk).update(status=status)
                self.authenticate(self.admin)
                self.assertEqual(self.client.get(self.url('center', 'dar')).data['state'], state)


class DashboardAndSettingsTests(CenterAccessMixin, APITestCase):
    """Center admins only, operational centers only."""

    def test_dashboard(self):
        self.authenticate(self.admin)
        response = self.client.get(self.url('center-dashboard', 'dar'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['members'], {'total': 2, 'center_admins': 1, 'specialists': 1})

    def test_specialist_gets_403_with_code(self):
        self.authenticate(self.specialist)
        for name in ('center-dashboard', 'center-settings'):
            with self.subTest(endpoint=name):
                self.assertError(self.client.get(self.url(name, 'dar')), 403, 'not_center_admin')

    def test_non_operational_center_is_blocked(self):
        self.authenticate(self.admin)
        for update in ({'status': Center.Status.PENDING}, {'status': Center.Status.REJECTED},
                       {'status': Center.Status.APPROVED, 'is_active': False}):
            Center.objects.filter(pk=self.center.pk).update(**update)
            for name in ('center-dashboard', 'center-settings'):
                with self.subTest(update=update, endpoint=name):
                    self.assertError(self.client.get(self.url(name, 'dar')), 403, 'center_not_operational')

    def test_non_member_gets_404_and_anonymous_401(self):
        for name in ('center-dashboard', 'center-settings'):
            with self.subTest(endpoint=name):
                self.client.force_authenticate(None)
                self.assertError(self.client.get(self.url(name, 'dar')), 401, 'not_authenticated')
                self.authenticate()
                self.assertError(self.client.get(self.url(name, 'dar')), 404, 'not_found')

    def test_patch_settings(self):
        self.authenticate(self.admin)
        response = self.client.patch(self.url('center-settings', 'dar'), {
            'description': 'Fatwa center.', 'languages': ['ar', 'fr'], 'name': 'Renamed', 'status': 'rejected',
            'telegram_chat_id': -100999,
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.center.refresh_from_db()
        self.assertEqual((self.center.description, self.center.languages), ('Fatwa center.', ['ar', 'fr']))
        self.assertEqual((self.center.name, self.center.status), ('Dar al-Ifta', Center.Status.APPROVED))
        self.assertIsNone(self.center.telegram_chat_id)  # connected only through the bot (ADR 0023)

    def test_settings_validation_has_codes(self):
        self.authenticate(self.admin)
        response = self.client.patch(self.url('center-settings', 'dar'), {'languages': ['de']}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['codes']['languages'], {0: ['invalid_choice']})


class LanguageTests(CenterAccessMixin, APITestCase):
    """Messages follow Accept-Language; codes never change."""

    def tearDown(self):
        translation.activate('en')

    def test_error_message_is_translated_and_code_is_stable(self):
        self.authenticate(self.specialist)
        for language, text in (('ar', 'لا يستطيع القيام بهذا إلا مسؤول المركز.'),
                               ('fr', 'Seul un administrateur du centre peut effectuer cette action.')):
            with self.subTest(language=language):
                response = self.client.get(self.url('center-dashboard', 'dar'), HTTP_ACCEPT_LANGUAGE=language)
                self.assertEqual((response.data['detail'], response.data['code']), (text, 'not_center_admin'))
