"""Tests for the OpenAPI schema and the docs page."""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase


class SchemaTests(TestCase):
    """The schema generates without a single warning; docs use local assets."""

    def test_schema_has_no_warnings(self):
        # --fail-on-warn makes any warning an error, so a new endpoint without
        # proper annotations fails here.
        call_command('spectacular', '--validate', '--fail-on-warn', '--file', '/dev/null', stderr=StringIO())

    def test_schema_endpoint_lists_only_public_identifiers(self):
        schema = self.client.get('/api/schema/', HTTP_ACCEPT='application/json').json()
        paths = set(schema['paths'])
        self.assertIn('/api/v1/centers/{slug}/memberships/{uuid}/offboard/', paths)
        self.assertFalse([path for path in paths if '{id}' in path or '{pk}' in path])

    def test_docs_page_uses_sidecar_assets(self):
        response = self.client.get('/api/docs/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/static/drf_spectacular_sidecar/')
        self.assertNotContains(response, 'cdn.jsdelivr.net')
