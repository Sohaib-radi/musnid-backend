"""Tests for the CORS policy (ADR 0012)."""

from django.test import override_settings

from api.tests.base import APITestCase

ORIGIN = 'https://app.example.org'


@override_settings(CORS_ALLOWED_ORIGINS=[ORIGIN])
class CorsTests(APITestCase):
    """Listed origins only, /api/ only, no credentials."""

    def preflight(self, path, origin=ORIGIN):
        return self.client.options(path, HTTP_ORIGIN=origin, HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST')

    def test_allowed_origin_on_api(self):
        response = self.preflight(self.url('login'))
        self.assertEqual(response['Access-Control-Allow-Origin'], ORIGIN)
        self.assertNotIn('Access-Control-Allow-Credentials', response)

    def test_other_origin_is_refused(self):
        self.assertNotIn('Access-Control-Allow-Origin', self.preflight(self.url('login'), 'https://evil.example'))

    def test_admin_has_no_cors(self):
        self.assertNotIn('Access-Control-Allow-Origin', self.preflight('/admin/login/'))

    def test_error_responses_carry_cors_headers(self):
        response = self.client.get(self.url('me'), HTTP_ORIGIN=ORIGIN)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response['Access-Control-Allow-Origin'], ORIGIN)

