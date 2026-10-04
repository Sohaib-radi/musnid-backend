"""Tests for core/crypto.py."""

from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from core import crypto

OLD, NEW = Fernet.generate_key().decode(), Fernet.generate_key().decode()


class CryptoTests(SimpleTestCase):
    """Round trip, rotation, missing and invalid keys, invalid tokens."""

    @override_settings(FIELD_ENCRYPTION_KEYS=[NEW])
    def test_round_trip_and_ciphertext_differs(self):
        token = crypto.encrypt('sk-secret-value-123456')
        self.assertNotIn('sk-secret', token)
        self.assertEqual(crypto.decrypt(token), 'sk-secret-value-123456')

    def test_rotation_new_key_encrypts_old_key_still_decrypts(self):
        with self.settings(FIELD_ENCRYPTION_KEYS=[OLD]):
            old_token = crypto.encrypt('old secret')
        with self.settings(FIELD_ENCRYPTION_KEYS=[NEW, OLD]):
            self.assertEqual(crypto.decrypt(old_token), 'old secret')
            new_token = crypto.encrypt('new secret')
        with self.settings(FIELD_ENCRYPTION_KEYS=[NEW]):
            self.assertEqual(crypto.decrypt(new_token), 'new secret')
            with self.assertRaises(ValueError):
                crypto.decrypt(old_token)

    @override_settings(FIELD_ENCRYPTION_KEYS=[])
    def test_missing_key(self):
        for call, value in ((crypto.encrypt, 'x'), (crypto.decrypt, 'x')):
            with self.subTest(call=call.__name__), self.assertRaises(ImproperlyConfigured):
                call(value)

    @override_settings(FIELD_ENCRYPTION_KEYS=['not-a-fernet-key'])
    def test_invalid_key(self):
        with self.assertRaises(ImproperlyConfigured):
            crypto.encrypt('x')

    @override_settings(FIELD_ENCRYPTION_KEYS=[NEW])
    def test_invalid_token_message_does_not_echo_it(self):
        with self.assertRaises(ValueError) as caught:
            crypto.decrypt('garbage-token-value')
        self.assertNotIn('garbage-token-value', str(caught.exception))
