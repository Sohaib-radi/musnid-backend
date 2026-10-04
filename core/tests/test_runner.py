"""Tests for ``core.tests.runner`` and ``core.tests.parallel``: the project's test runner."""

import subprocess
import sys

from django.conf import settings
from django.contrib.auth.hashers import get_hasher
from django.db import connection
from django.test import TestCase

from core.tests.parallel import TEST_PASSWORD_HASHERS
from core.tests.support import TEST_ONLY_MODELS


class TestRunnerTests(TestCase):
    """The runner prepared this test database and environment."""

    def test_test_only_tables_exist(self):
        tables = set(connection.introspection.table_names())
        for model in TEST_ONLY_MODELS:
            with self.subTest(model=model.__name__):
                self.assertIn(model._meta.db_table, tables)

    def test_fast_password_hasher_is_active(self):
        self.assertEqual(settings.PASSWORD_HASHERS, TEST_PASSWORD_HASHERS)
        self.assertEqual(get_hasher().algorithm, 'md5')

    def test_parallel_module_imports_before_django_setup(self):
        # Spawned workers import core.tests.parallel before django.setup();
        # if it pulled in models, every worker would crash and the run hang.
        result = subprocess.run(
            [sys.executable, '-c', 'import core.tests.parallel'],
            cwd=settings.BASE_DIR, capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
