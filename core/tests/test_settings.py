"""
Tests for how ``config.settings`` reads the environment.

Settings are evaluated once per process, so each case imports
``config.settings`` in a fresh Python subprocess with a controlled
environment. Required variables are always passed explicitly, so the tests do
not depend on the developer's ``.env``; a variable is "removed" by passing it
empty, which python-dotenv will not override and ``config.env`` treats as unset.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

BASE_DIR = Path(__file__).resolve().parents[2]

REQUIRED = {
    'DJANGO_SECRET_KEY': 'test-secret',
    'POSTGRES_DB': 'test_db',
    'POSTGRES_USER': 'test_user',
    'POSTGRES_PASSWORD': 'test_password',
}

# Prints the settings under test as JSON so the parent can assert on them.
PROBE = (
    'import json, config.settings as s; '
    'db = s.DATABASES["default"]; '
    'print(json.dumps({"DEBUG": s.DEBUG, "ALLOWED_HOSTS": s.ALLOWED_HOSTS, '
    '"ENGINE": db["ENGINE"], "HOST": db["HOST"], "PORT": db["PORT"]}))'
)


def import_settings(**overrides):
    """
    Import ``config.settings`` in a subprocess and return the completed process.

    Args:
        **overrides: Environment variables to set on top of ``REQUIRED``.
            Optional variables not given are passed empty so the developer's
            ``.env`` cannot leak into the result.
    """
    environ = {**os.environ, **REQUIRED}
    for name in ('DJANGO_DEBUG', 'DJANGO_ALLOWED_HOSTS', 'POSTGRES_HOST', 'POSTGRES_PORT'):
        environ[name] = ''
    environ.update(overrides)
    return subprocess.run(
        [sys.executable, '-c', PROBE],
        cwd=BASE_DIR, env=environ, capture_output=True, text=True, timeout=60,
    )


def load_settings(**overrides):
    """Import settings in a subprocess and return the probed values as a dict."""
    result = import_settings(**overrides)
    if result.returncode != 0:
        raise AssertionError(f'settings import failed:\n{result.stderr}')
    return json.loads(result.stdout)


class RequiredVariableTests(SimpleTestCase):
    """Importing settings fails clearly when a required variable is missing."""

    def test_each_missing_variable_fails_with_its_name(self):
        for name in REQUIRED:
            with self.subTest(variable=name):
                result = import_settings(**{name: ''})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('ImproperlyConfigured', result.stderr)
                self.assertIn(f'Required environment variable {name} is not set', result.stderr)

    def test_imports_when_all_required_variables_are_set(self):
        self.assertEqual(import_settings().returncode, 0)


class DebugParsingTests(SimpleTestCase):
    """Only the exact string ``True`` turns ``DEBUG`` on."""

    def test_exact_true_enables_debug(self):
        self.assertIs(load_settings(DJANGO_DEBUG='True')['DEBUG'], True)

    def test_other_values_leave_debug_off(self):
        for value in ('true', '1', 'yes', 'False', ''):
            with self.subTest(value=value):
                self.assertIs(load_settings(DJANGO_DEBUG=value)['DEBUG'], False)


class OptionalVariableTests(SimpleTestCase):
    """Optional variables have the documented defaults and can be overridden."""

    def test_defaults(self):
        values = load_settings()
        self.assertEqual(values['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual(values['HOST'], 'localhost')
        self.assertEqual(values['PORT'], '5435')
        self.assertEqual(values['ALLOWED_HOSTS'], [])

    def test_overrides(self):
        values = load_settings(
            POSTGRES_HOST='db', POSTGRES_PORT='5432',
            DJANGO_ALLOWED_HOSTS='localhost, 127.0.0.1',
        )
        self.assertEqual(values['HOST'], 'db')
        self.assertEqual(values['PORT'], '5432')
        self.assertEqual(values['ALLOWED_HOSTS'], ['localhost', '127.0.0.1'])
