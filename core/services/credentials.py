"""
Adding, revoking and reading provider API keys (ADR 0014).

Secrets never leave this module except as the return value of
``get_secret``/``get_openai_key``, for the code that calls the provider. They
are never logged, printed, displayed or put in an exception message; every
function handling one is marked with ``sensitive_variables`` so Django's
error reports redact it. Codes:

* ``invalid_format``: the key does not look like a key of that provider.
* ``duplicate_secret``: the key was already added (even if since revoked).
"""

import hashlib

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.debug import sensitive_variables

from core import crypto
from core.models import ApiCredential

OPENAI_PREFIX = 'sk-'
MIN_LENGTH = 20


@sensitive_variables('secret')
def fingerprint(secret):
    """SHA-256 hex digest of ``secret``, used to refuse a key added twice."""
    return hashlib.sha256(secret.encode()).hexdigest()


@sensitive_variables('secret')
def validate_secret(provider, secret):
    """
    Check the format of ``secret`` for ``provider`` and that it is new.

    Raises:
        ValidationError: ``invalid_format`` or ``duplicate_secret``. Messages
            never contain the secret.
    """
    if provider == ApiCredential.Provider.OPENAI:
        if not secret.startswith(OPENAI_PREFIX) or len(secret) < MIN_LENGTH or any(c.isspace() for c in secret):
            raise ValidationError(
                _('This does not look like an OpenAI API key: it must start with “sk-”, '
                  'have at least 20 characters and no spaces.'),
                code='invalid_format',
            )
    if ApiCredential.objects.filter(fingerprint=fingerprint(secret)).exists():
        raise ValidationError(_('This API key was already added.'), code='duplicate_secret')


@sensitive_variables('secret')
def add_credential(provider, name, secret, created_by=None):
    """
    Store a new key for ``provider`` and make it the active one.

    The previous active key of the provider is revoked in the same
    transaction, under a row lock, so there is never a moment with two
    active keys or none.

    Raises:
        ValidationError: see ``validate_secret``.
        ImproperlyConfigured: no encryption key configured.
    """
    secret = secret.strip()
    validate_secret(provider, secret)
    with transaction.atomic():
        for previous in ApiCredential.objects.select_for_update().filter(provider=provider, is_active=True):
            _revoke(previous, created_by)
        return ApiCredential.objects.create(
            provider=provider,
            name=name.strip(),
            encrypted_secret=crypto.encrypt(secret),
            fingerprint=fingerprint(secret),
            prefix=secret[:3],
            last_four=secret[-4:],
            created_by=created_by,
        )


def revoke(credential, revoked_by=None):
    """Revoke ``credential``. Revoking a revoked key changes nothing."""
    with transaction.atomic():
        locked = ApiCredential.objects.select_for_update().get(pk=credential.pk)
        if locked.is_active:
            _revoke(locked, revoked_by)
    credential.refresh_from_db()
    return credential


@sensitive_variables('secret')
def get_secret(provider):
    """
    Return the plaintext key for ``provider``, or '' when there is none.

    The active key added in the admin wins; for OpenAI the fallback is
    ``settings.OPENAI_API_KEY``. Only code that calls the provider may use this.
    """
    active = ApiCredential.objects.filter(provider=provider, is_active=True).first()
    if active is not None:
        return crypto.decrypt(active.encrypted_secret)
    if provider == ApiCredential.Provider.OPENAI:
        return settings.OPENAI_API_KEY
    return ''


@sensitive_variables('secret')
def get_openai_key():
    """The OpenAI key to use: the active admin key, else ``settings.OPENAI_API_KEY``."""
    return get_secret(ApiCredential.Provider.OPENAI)


def _revoke(credential, revoked_by):
    credential.is_active = False
    credential.revoked_at = timezone.now()
    credential.revoked_by = revoked_by
    credential.save(update_fields=['is_active', 'revoked_at', 'revoked_by', 'updated_at'])
