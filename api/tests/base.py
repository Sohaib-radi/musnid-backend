"""Base test case for API tests."""

from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APITestCase as DRFAPITestCase

from core.tests.support import make_user


class APITestCase(DRFAPITestCase):
    """
    DRF test case with helpers.

    The cache is cleared before each test because throttling counts requests
    in it; without this, auth tests would throttle each other.
    """

    def setUp(self):
        super().setUp()
        cache.clear()

    def url(self, name, *args):
        """Reverse an API v1 URL name, e.g. ``self.url('center', 'dar')``."""
        return reverse(f'v1:{name}', args=args)

    def authenticate(self, user=None, **fields):
        """Authenticate the client as ``user`` (created if omitted) and return it."""
        user = user or make_user(**fields)
        self.client.force_authenticate(user)
        return user

    def assertError(self, response, status, code):
        """Assert a single-message error: the status, and ``code`` next to ``detail``."""
        self.assertEqual(response.status_code, status, response.data)
        self.assertEqual(response.data['code'], code)
        self.assertIn('detail', response.data)
