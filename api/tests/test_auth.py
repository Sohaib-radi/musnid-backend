"""Tests for the auth endpoints: registration, login, refresh, logout, throttling."""

from django.test import override_settings
from rest_framework_simplejwt.tokens import AccessToken

from api.tests.base import APITestCase
from core.models import Center, Membership, User
from core.tests.support import make_center, make_user

PASSWORD = 'a-Long-pass-123'


class RegisterTests(APITestCase):
    """POST auth/register/: an asker account, logged in on success."""

    def test_registers_and_returns_tokens(self):
        response = self.client.post(self.url('register'), {
            'email': 'amina@example.com', 'full_name': 'Amina', 'password': PASSWORD, 'preferred_lang': 'ar',
        })
        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(email='amina@example.com')
        self.assertEqual(response.data['user']['uuid'], str(user.uuid))
        self.assertNotIn('id', response.data['user'])
        self.assertEqual(AccessToken(response.data['access'])['user_uuid'], str(user.uuid))
        self.assertEqual(user.preferred_lang, 'ar')
        self.assertFalse(user.memberships.exists())

    def test_email_taken_in_any_case(self):
        make_user(email='amina@example.com')
        response = self.client.post(self.url('register'), {
            'email': 'AMINA@example.com', 'full_name': 'A', 'password': PASSWORD,
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['codes']['email'], ['email_taken'])

    def test_weak_password_is_refused_with_codes(self):
        response = self.client.post(self.url('register'), {
            'email': 'amina@example.com', 'full_name': 'Amina', 'password': '123',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('password_too_short', response.data['codes']['password'])


class CenterRegisterTests(APITestCase):
    """POST auth/register/center/: account plus a pending center."""

    def payload(self, **center):
        return {
            'email': 'amina@example.com', 'full_name': 'Amina', 'password': PASSWORD,
            'center': {'name': 'Dar al-Ifta', 'country': 'ma', 'languages': ['ar', 'fr'], **center},
        }

    def test_creates_pending_center_with_applicant_as_admin(self):
        response = self.client.post(self.url('register-center'), self.payload(), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        center = Center.objects.get(slug='dar-al-ifta')
        self.assertEqual(center.status, Center.Status.PENDING)
        self.assertEqual(center.country.code, 'MA')
        self.assertEqual(response.data['center']['state'], 'pending_review')
        membership = Membership.objects.get(center=center)
        self.assertEqual(membership.user.email, 'amina@example.com')
        self.assertEqual(membership.role, Membership.Role.CENTER_ADMIN)

    def test_center_name_taken(self):
        make_center(name='Dar al-Ifta')
        response = self.client.post(self.url('register-center'), self.payload(), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['codes']['center']['name'], ['center_name_taken'])
        self.assertFalse(User.objects.filter(email='amina@example.com').exists())

    def test_unknown_country(self):
        response = self.client.post(self.url('register-center'), self.payload(country='XX'), format='json')
        self.assertEqual(response.data['codes']['center']['country'], ['invalid_country'])


class TokenTests(APITestCase):
    """Login, refresh with rotation and blacklist, logout."""

    def setUp(self):
        super().setUp()
        self.user = make_user(email='amina@example.com', password=PASSWORD)

    def login(self, email='amina@example.com', password=PASSWORD):
        return self.client.post(self.url('login'), {'email': email, 'password': password})

    def test_login_with_any_email_case(self):
        response = self.login(email='AMINA@Example.com')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(AccessToken(response.data['access'])['user_uuid'], str(self.user.uuid))
        self.assertNotIn('user_id', AccessToken(response.data['access']).payload)

    def test_wrong_password_is_401_with_code(self):
        self.assertError(self.login(password='wrong'), 401, 'no_active_account')

    def test_refresh_rotates_and_blacklists_the_old_token(self):
        refresh = self.login().data['refresh']
        response = self.client.post(self.url('refresh'), {'refresh': refresh})
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.data['refresh'], refresh)
        self.assertError(self.client.post(self.url('refresh'), {'refresh': refresh}), 401, 'token_not_valid')

    def test_logout_blacklists_the_refresh_token(self):
        tokens = self.login().data
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
        self.assertEqual(self.client.post(self.url('logout'), {'refresh': tokens['refresh']}).status_code, 200)
        self.assertError(self.client.post(self.url('refresh'), {'refresh': tokens['refresh']}), 401, 'token_not_valid')

    def test_logout_requires_authentication(self):
        refresh = self.login().data['refresh']
        self.assertError(self.client.post(self.url('logout'), {'refresh': refresh}), 401, 'not_authenticated')


class ThrottleTests(APITestCase):
    """Login, registration and refresh share the "auth" scope: 10 per minute."""

    def test_eleventh_request_in_a_minute_is_throttled(self):
        for _attempt in range(10):
            self.client.post(self.url('login'), {'email': 'x@example.com', 'password': 'x'})
        self.assertError(self.client.post(self.url('login'), {'email': 'x@example.com', 'password': 'x'}),
                         429, 'throttled')

    def test_registration_and_refresh_are_throttled(self):
        for name in ('register', 'refresh'):
            with self.subTest(endpoint=name):
                self.setUp()  # fresh cache per endpoint
                for _attempt in range(10):
                    self.client.post(self.url(name), {})
                self.assertEqual(self.client.post(self.url(name), {}).status_code, 429)

    @override_settings(LANGUAGE_CODE='en')
    def test_profile_is_not_throttled(self):
        self.authenticate()
        for _attempt in range(12):
            response = self.client.get(self.url('me'))
        self.assertEqual(response.status_code, 200)
