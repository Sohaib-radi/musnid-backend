"""
Tests for ``core/migrations``: the pgvector extension and migration completeness.
"""

from django.apps import apps
from django.db import connection
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.state import ProjectState
from django.test import TestCase
from pgvector.django import VectorExtension

from core.tests.support import TEST_ONLY_MODELS


class VectorExtensionTests(TestCase):
    """The initial migration enables pgvector before anything else."""

    def test_vector_extension_is_installed(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            self.assertIsNotNone(cursor.fetchone(), 'the vector extension is not installed')

    def test_vector_type_is_usable(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT '[1,2,3]'::vector <-> '[1,2,4]'::vector")
            self.assertEqual(cursor.fetchone()[0], 1.0)

    def test_vector_extension_is_the_first_operation(self):
        loader = MigrationLoader(None, ignore_no_migrations=True)
        initial = loader.get_migration('core', '0001_initial')
        self.assertIsInstance(initial.operations[0], VectorExtension)


class MigrationCompletenessTests(TestCase):
    """Every model change has a migration (test-only models excepted)."""

    def test_no_missing_migrations(self):
        loader = MigrationLoader(None, ignore_no_migrations=True)
        changes = MigrationAutodetector(
            loader.project_state(), ProjectState.from_apps(apps),
        ).changes(graph=loader.graph)
        test_only = {model._meta.model_name for model in TEST_ONLY_MODELS}
        missing = [
            f'{app}: {operation.describe()}'
            for app, migrations in changes.items()
            for migration in migrations
            for operation in migration.operations
            if getattr(operation, 'name_lower', None) not in test_only
        ]
        self.assertEqual(missing, [], 'run makemigrations')
