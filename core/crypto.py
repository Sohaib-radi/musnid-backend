"""
Symmetric encryption of secrets stored in the database (ADR 0014).

Uses Fernet (AES-128-CBC with HMAC-SHA256) through ``MultiFernet`` over
``settings.FIELD_ENCRYPTION_KEYS``: the first key encrypts, every key
decrypts. To rotate, put a new key first, re-encrypt (or re-add) the secrets,
then drop the old key. ``SECRET_KEY`` is never used.
"""

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.views.decorators.debug import sensitive_variables


def _fernet():
    keys = settings.FIELD_ENCRYPTION_KEYS
    if not keys:
        raise ImproperlyConfigured(
            'FIELD_ENCRYPTION_KEYS is not set. Generate a key with '
            '"python -c \'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\'".'
        )
    try:
        return MultiFernet([Fernet(key) for key in keys])
    except ValueError as error:
        raise ImproperlyConfigured('FIELD_ENCRYPTION_KEYS contains an invalid Fernet key.') from error


@sensitive_variables('plaintext')
def encrypt(plaintext):
    """
    Encrypt ``plaintext`` (str) with the newest key; return the token as str.

    Raises:
        ImproperlyConfigured: If no valid key is configured.
    """
    return _fernet().encrypt(plaintext.encode()).decode()


@sensitive_variables('plaintext')
def decrypt(token):
    """
    Decrypt a token produced by ``encrypt`` with any configured key.

    Raises:
        ImproperlyConfigured: If no valid key is configured.
        ValueError: If the token is invalid or no configured key decrypts it.
            The message never includes the token.
    """
    try:
        plaintext = _fernet().decrypt(token.encode())
    except InvalidToken:
        raise ValueError('The encrypted value cannot be decrypted with the configured keys.') from None
    return plaintext.decode()
