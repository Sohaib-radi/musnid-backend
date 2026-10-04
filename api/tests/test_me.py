"""Tests for me/ and me/memberships/."""

from django.utils import timezone, translation

from api.tests.base import APITestCase
from core.models import Center, Membership
from core.tests.support import make_center, make_membership


class MeTests(APITestCase):
    """GET and PATCH the caller's profile."""

    def test_requires_authentication(self):
        self.assertError(self.client.get(self.url('me')), 401, 'not_authenticated')

    def test_get(self):
        user = self.authenticate(email='amina@example.com')
        response = self.client.get(self.url('me'))
        self.assertEqual(response.data['uuid'], str(user.uuid))
        self.assertEqual(response.data['email'], 'amina@example.com')
        self.assertFalse(response.data['telegram_linked'])

    def test_patch_changes_profile_but_not_email(self):
        user = self.authenticate(email='amina@example.com')
        response = self.client.patch(self.url('me'), {
            'full_name': 'Amina B.', 'preferred_lang': 'fr', 'email': 'other@example.com',
        })
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual((user.full_name, user.preferred_lang, user.email), ('Amina B.', 'fr', 'amina@example.com'))

    def test_put_is_not_allowed(self):
        self.authenticate()
        self.assertError(self.client.put(self.url('me'), {}), 405, 'method_not_allowed')


class MyMembershipsTests(APITestCase):
    """GET me/memberships/: each center's state for frontend routing."""

    def test_requires_authentication(self):
        self.assertError(self.client.get(self.url('my-memberships')), 401, 'not_authenticated')

    def test_states(self):
        user = self.authenticate()
        expected = {
            'pending_review': make_center(status=Center.Status.PENDING),
            'rejected': make_center(status=Center.Status.REJECTED, rejection_reason='Incomplete.'),
            'suspended': make_center(is_active=False),
            'operational': make_center(),
        }
        for center in expected.values():
            make_membership(user=user, center=center)
        make_membership()  # someone else's
        response = self.client.get(self.url('my-memberships'))
        states = {item['center']['slug']: item['center']['state'] for item in response.data['results']}
        self.assertEqual(states, {center.slug: state for state, center in expected.items()})
        rejected = next(i for i in response.data['results'] if i['center']['state'] == 'rejected')
        self.assertEqual(rejected['center']['rejection_reason'], 'Incomplete.')

    def test_ended_memberships_come_last(self):
        user = self.authenticate()
        ended = make_membership(user=user, is_active=False, left_at=timezone.now())
        active = make_membership(user=user)
        uuids = [item['uuid'] for item in self.client.get(self.url('my-memberships')).data['results']]
        self.assertEqual(uuids, [str(active.uuid), str(ended.uuid)])


class CountriesTests(APITestCase):
    """GET countries/: public, translated names."""

    def test_public_and_translated(self):
        for language, name in (('en', 'Morocco'), ('fr', 'Maroc'), ('ar', 'المغرب')):
            with self.subTest(language=language):
                response = self.client.get(self.url('countries'), HTTP_ACCEPT_LANGUAGE=language)
                self.assertEqual(response.status_code, 200)
                self.assertIn({'code': 'MA', 'name': name}, response.data)

    def tearDown(self):
        translation.activate('en')
