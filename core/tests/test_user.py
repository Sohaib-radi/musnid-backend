"""Tests for ``core.models.user``: the email-based custom user."""

import uuid

from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from core.models import Language, User
from core.tests.support import make_user


class UserModelTests(TestCase):
    """Field defaults, identity and string form."""

    def test_is_the_configured_user_model(self):
        self.assertIs(get_user_model(), User)

    def test_defaults(self):
        user = make_user()
        self.assertIsInstance(user.uuid, uuid.UUID)
        self.assertEqual(user.preferred_lang, Language.ENGLISH)
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_verified)
        self.assertIsNone(user.telegram_chat_id)
        self.assertFalse(user.avatar)

    def test_uuid_is_unique_per_user(self):
        self.assertNotEqual(make_user().uuid, make_user().uuid)

    def test_str_and_names(self):
        user = make_user(email='amina@example.com', full_name='Amina Benali')
        self.assertEqual(str(user), 'amina@example.com')
        self.assertEqual(user.get_full_name(), 'Amina Benali')
        self.assertEqual(user.get_short_name(), 'Amina Benali')

    def test_telegram_chat_id_is_unique(self):
        make_user(telegram_chat_id=123456789)
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_user(telegram_chat_id=123456789)

    def test_several_users_without_telegram_chat_id(self):
        make_user()
        make_user()
        self.assertEqual(User.objects.filter(telegram_chat_id__isnull=True).count(), 2)


class EmailUniquenessTests(TestCase):
    """Email is unique regardless of case, in the database and in validation."""

    def test_same_email_different_case_violates_constraint(self):
        make_user(email='amina@example.com')
        with self.assertRaises(IntegrityError) as caught, transaction.atomic():
            make_user(email='Amina@example.com')
        self.assertIn('unique_user_email_ci', str(caught.exception))

    def test_full_clean_reports_translated_constraint_message(self):
        make_user(email='amina@example.com')
        duplicate = User(email='AMINA@example.com', full_name='Other')
        duplicate.set_unusable_password()
        with self.assertRaises(ValidationError) as caught:
            duplicate.full_clean()
        self.assertIn('A user with this email address already exists.', caught.exception.messages)


class UserManagerTests(TestCase):
    """``create_user`` and ``create_superuser``."""

    def test_create_user(self):
        user = User.objects.create_user('Amina@EXAMPLE.com', 'Amina', password='s3cret-pass')
        self.assertEqual(user.email, 'Amina@example.com')  # domain lower-cased only
        self.assertTrue(user.check_password('s3cret-pass'))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_user_without_password_is_unusable(self):
        self.assertFalse(User.objects.create_user('a@example.com', 'A').has_usable_password())

    def test_create_user_requires_email(self):
        with self.assertRaises(ValueError):
            User.objects.create_user('', 'Nobody')

    def test_create_superuser(self):
        user = User.objects.create_superuser('root@example.com', 'Root', password='s3cret-pass')
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_create_superuser_rejects_false_flags(self):
        for flag in ('is_staff', 'is_superuser'):
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                User.objects.create_superuser('root@example.com', 'Root', **{flag: False})


class EmailLoginTests(TestCase):
    """Login uses the email and ignores its case."""

    def setUp(self):
        self.user = make_user(email='amina@example.com', password='s3cret-pass')

    def test_login_with_exact_email(self):
        self.assertEqual(authenticate(username='amina@example.com', password='s3cret-pass'), self.user)

    def test_login_ignores_email_case(self):
        self.assertEqual(authenticate(username='AMINA@Example.COM', password='s3cret-pass'), self.user)

    def test_wrong_password_fails(self):
        self.assertIsNone(authenticate(username='amina@example.com', password='wrong'))

    def test_inactive_user_cannot_log_in(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active', 'updated_at'])
        self.assertIsNone(authenticate(username='amina@example.com', password='s3cret-pass'))

    def test_natural_key_lookup_ignores_case(self):
        self.assertEqual(User.objects.get_by_natural_key('Amina@Example.com'), self.user)
