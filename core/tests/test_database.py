"""
Tests against the real PostgreSQL test database.

These run on the database Django creates for the test run (``test_`` plus
``POSTGRES_DB``), so the configured role needs the CREATEDB privilege, which
the Compose ``db`` service grants by default.
"""

from django.db import connection
from django.test import TestCase


class DatabaseConnectionTests(TestCase):
    """The configured database is reachable PostgreSQL with pgvector available."""

    def test_backend_is_postgresql(self):
        self.assertEqual(connection.vendor, 'postgresql')

    def test_query_round_trip(self):
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            self.assertEqual(cursor.fetchone(), (1,))

    def test_vector_extension_is_available(self):
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT default_version FROM pg_available_extensions WHERE name = %s',
                ['vector'],
            )
            self.assertIsNotNone(cursor.fetchone(), 'pgvector is not installed on the server')

    def test_vector_extension_can_be_enabled_and_used(self):
        # Enabling happens inside the test transaction and is rolled back;
        # enabling it permanently is left to the migration that first needs it.
        with connection.cursor() as cursor:
            cursor.execute('CREATE EXTENSION IF NOT EXISTS vector')
            cursor.execute("SELECT '[1,2,3]'::vector <-> '[1,2,4]'::vector")
            self.assertEqual(cursor.fetchone()[0], 1.0)
