"""
Provider API keys, stored encrypted (ADR 0014).

Only the encrypted value, a SHA-256 fingerprint (to refuse duplicates) and a
masked form (first 3 and last 4 characters) are stored. Keys are created and
revoked only through ``core.services.credentials``; they are never edited.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from .base import BaseModel, CreatedByMixin


class ApiCredential(BaseModel, CreatedByMixin):
    """An encrypted API key of an external provider; at most one active per provider."""

    class Provider(models.TextChoices):
        """Providers. Labels are brand names and are not translated."""

        OPENAI = 'openai', 'OpenAI'

    provider = models.CharField(_('provider'), max_length=20, choices=Provider.choices)
    name = models.CharField(_('name'), max_length=100, help_text=_('For example: production key.'))
    encrypted_secret = models.TextField(_('encrypted secret'), editable=False)
    fingerprint = models.CharField(_('fingerprint'), max_length=64, unique=True, editable=False)
    prefix = models.CharField(_('prefix'), max_length=3, editable=False)
    last_four = models.CharField(_('last four characters'), max_length=4, editable=False)
    is_active = models.BooleanField(_('active'), default=True, editable=False)
    revoked_at = models.DateTimeField(_('revoked at'), null=True, blank=True, editable=False)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        editable=False,
        verbose_name=_('revoked by'),
    )

    class Meta(BaseModel.Meta):
        verbose_name = _('API key')
        verbose_name_plural = _('API keys')
        constraints = [
            models.UniqueConstraint(
                fields=['provider'],
                condition=models.Q(is_active=True),
                name='one_active_credential_per_provider',
                violation_error_message=_('This provider already has an active API key.'),
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(is_active=True, revoked_at__isnull=True)
                    | models.Q(is_active=False, revoked_at__isnull=False)
                ),
                name='credential_active_matches_revoked_at',
                violation_error_message=_('An active API key cannot have a revocation date, and a revoked one must have one.'),
            ),
        ]

    @property
    def masked(self):
        """The key as it may be displayed, e.g. ``sk-...abcd``."""
        return f'{self.prefix}...{self.last_four}'

    def __str__(self):
        return f'{self.name} ({self.masked})'

    def __repr__(self):
        # Never the encrypted value or the fingerprint: only what may be displayed.
        return f'<ApiCredential {self.provider} {self.masked}>'
