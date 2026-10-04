"""Tests for core/services/credentials.py."""

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from core import crypto
from core.models import ApiCredential
from core.services import credentials
from core.tests.support import TEST_ENCRYPTION_KEYS, make_credential, make_openai_key, make_user


@override_settings(FIELD_ENCRYPTION_KEYS=TEST_ENCRYPTION_KEYS, OPENAI_API_KEY='')
class CredentialServiceTests(TestCase):
    """Validation, adding with rotation, revoking, reading."""

    def assertCode(self, code, secret):
        with self.assertRaises(ValidationError) as caught:
            credentials.validate_secret('openai', secret)
        self.assertEqual(caught.exception.code, code)
        self.assertNotIn(secret, ' '.join(caught.exception.messages))

    def test_invalid_formats(self):
        for secret in ('pk-0123456789abcdefghij', 'sk-short', 'sk-0123456789 abcdefghij'):
            with self.subTest(secret=secret):
                self.assertCode('invalid_format', secret)

    def test_duplicate_even_when_revoked(self):
        secret = make_openai_key()
        credentials.revoke(make_credential(secret=secret))
        self.assertCode('duplicate_secret', secret)

    def test_add_strips_encrypts_and_stores_only_derived_values(self):
        user = make_user()
        secret = make_openai_key()
        credential = credentials.add_credential('openai', '  Production  ', f'  {secret}\n', created_by=user)
        self.assertEqual(credential.name, 'Production')
        self.assertEqual(crypto.decrypt(credential.encrypted_secret), secret)
        self.assertEqual((credential.prefix, credential.last_four), (secret[:3], secret[-4:]))
        self.assertEqual(credential.fingerprint, credentials.fingerprint(secret))
        self.assertEqual(credential.created_by, user)
        stored = ApiCredential.objects.values().get(pk=credential.pk)
        self.assertFalse([value for value in stored.values() if value == secret])

    def test_add_revokes_the_previous_active_key(self):
        user = make_user()
        old = make_credential()
        new = credentials.add_credential('openai', 'New', make_openai_key(), created_by=user)
        old.refresh_from_db()
        self.assertFalse(old.is_active)
        self.assertIsNotNone(old.revoked_at)
        self.assertEqual(old.revoked_by, user)
        self.assertTrue(new.is_active)

    def test_revoke_is_idempotent(self):
        user = make_user()
        credential = credentials.revoke(make_credential(), user)
        revoked_at = credential.revoked_at
        credentials.revoke(credential, make_user())
        credential.refresh_from_db()
        self.assertEqual((credential.revoked_at, credential.revoked_by), (revoked_at, user))

    def test_get_openai_key_prefers_the_admin_key(self):
        secret = make_openai_key()
        make_credential(secret=secret)
        with self.settings(OPENAI_API_KEY='sk-from-environment-000000'):
            self.assertEqual(credentials.get_openai_key(), secret)

    def test_get_openai_key_falls_back_to_the_setting(self):
        with self.settings(OPENAI_API_KEY='sk-from-environment-000000'):
            self.assertEqual(credentials.get_openai_key(), 'sk-from-environment-000000')
            credentials.revoke(make_credential())
            self.assertEqual(credentials.get_openai_key(), 'sk-from-environment-000000')

    def test_get_secret_without_any_key(self):
        self.assertEqual(credentials.get_secret('openai'), '')
