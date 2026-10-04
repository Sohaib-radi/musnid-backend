"""Unit tests for the environment variable readers in ``config.env``."""

import os
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config import env


class RequiredTests(SimpleTestCase):
    """``env.required`` returns set values and rejects unset or empty ones."""

    def test_returns_value(self):
        with mock.patch.dict(os.environ, {'MUSNID_TEST_VAR': 'value'}):
            self.assertEqual(env.required('MUSNID_TEST_VAR'), 'value')

    def test_strips_surrounding_whitespace(self):
        with mock.patch.dict(os.environ, {'MUSNID_TEST_VAR': '  value  '}):
            self.assertEqual(env.required('MUSNID_TEST_VAR'), 'value')

    def test_unset_raises_with_variable_name(self):
        with mock.patch.dict(os.environ, clear=True):
            with self.assertRaisesMessage(ImproperlyConfigured, 'MUSNID_TEST_VAR'):
                env.required('MUSNID_TEST_VAR')

    def test_empty_is_treated_as_unset(self):
        for value in ('', '   '):
            with self.subTest(value=value), mock.patch.dict(os.environ, {'MUSNID_TEST_VAR': value}):
                with self.assertRaises(ImproperlyConfigured):
                    env.required('MUSNID_TEST_VAR')


class OptionalTests(SimpleTestCase):
    """``env.optional`` falls back to the default when unset or empty."""

    def test_returns_value(self):
        with mock.patch.dict(os.environ, {'MUSNID_TEST_VAR': 'db'}):
            self.assertEqual(env.optional('MUSNID_TEST_VAR', 'localhost'), 'db')

    def test_unset_returns_default(self):
        with mock.patch.dict(os.environ, clear=True):
            self.assertEqual(env.optional('MUSNID_TEST_VAR', 'localhost'), 'localhost')

    def test_empty_returns_default(self):
        with mock.patch.dict(os.environ, {'MUSNID_TEST_VAR': ''}):
            self.assertEqual(env.optional('MUSNID_TEST_VAR', 'localhost'), 'localhost')


class FlagTests(SimpleTestCase):
    """``env.flag`` is true only for the exact string ``True``."""

    def test_exact_true_is_true(self):
        with mock.patch.dict(os.environ, {'MUSNID_TEST_VAR': 'True'}):
            self.assertIs(env.flag('MUSNID_TEST_VAR'), True)

    def test_other_values_are_false(self):
        for value in ('true', 'TRUE', '1', 'yes', 'on', 'False', ''):
            with self.subTest(value=value), mock.patch.dict(os.environ, {'MUSNID_TEST_VAR': value}):
                self.assertIs(env.flag('MUSNID_TEST_VAR'), False)

    def test_unset_is_false(self):
        with mock.patch.dict(os.environ, clear=True):
            self.assertIs(env.flag('MUSNID_TEST_VAR'), False)


class CsvListTests(SimpleTestCase):
    """``env.csv_list`` splits on commas and drops blanks."""

    def test_splits_and_strips(self):
        with mock.patch.dict(os.environ, {'MUSNID_TEST_VAR': 'localhost, 127.0.0.1 ,,'}):
            self.assertEqual(env.csv_list('MUSNID_TEST_VAR'), ['localhost', '127.0.0.1'])

    def test_unset_is_empty_list(self):
        with mock.patch.dict(os.environ, clear=True):
            self.assertEqual(env.csv_list('MUSNID_TEST_VAR'), [])


class IntegerTests(SimpleTestCase):
    """``env.integer`` parses non-negative integers and rejects anything else."""

    def test_returns_value(self):
        with mock.patch.dict(os.environ, {'MUSNID_TEST_VAR': ' 150 '}):
            self.assertEqual(env.integer('MUSNID_TEST_VAR', 7), 150)

    def test_unset_or_empty_returns_default(self):
        for environ in ({}, {'MUSNID_TEST_VAR': ''}):
            with self.subTest(environ=environ), mock.patch.dict(os.environ, environ, clear=True):
                self.assertEqual(env.integer('MUSNID_TEST_VAR', 7), 7)

    def test_invalid_raises_with_variable_name(self):
        for value in ('-1', '1.5', 'ten'):
            with self.subTest(value=value), mock.patch.dict(os.environ, {'MUSNID_TEST_VAR': value}):
                with self.assertRaisesMessage(ImproperlyConfigured, 'MUSNID_TEST_VAR'):
                    env.integer('MUSNID_TEST_VAR', 7)
