"""
Tests against the real PostgreSQL test database.

These run on the database Django creates for the test run (``test_`` plus
``POSTGRES_DB``), so the configured role needs the CREATEDB privilege, which
the Compose ``db`` service grants by default. pgvector checks live in
``test_migrations``, since the extension is now enabled by a migration.
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

    def test_vector_extension_is_available_on_the_server(self):
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT default_version FROM pg_available_extensions WHERE name = %s',
                ['vector'],
            )
            self.assertIsNotNone(cursor.fetchone(), 'pgvector is not installed on the server')
