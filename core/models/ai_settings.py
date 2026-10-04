"""
AI configuration, editable in the admin (one row).

The crews read the chat model and temperature from here on each question, so
staff can switch models without a deployment. The API key itself comes from
``core.services.credentials`` (ADR 0014).
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from .base import BaseModel

DEFAULT_CHAT_MODEL = 'gpt-4o-mini'


class AISettings(BaseModel):
    """Singleton: always row 1, created on first use by ``AISettings.load()``."""

    chat_model = models.CharField(
        _('chat model'), max_length=100, default=DEFAULT_CHAT_MODEL,
        help_text=_('OpenAI model used by the crews, for example gpt-4o-mini.'),
    )
    temperature = models.DecimalField(_('temperature'), max_digits=3, decimal_places=2, default=0.2)
    verifier_model = models.CharField(
        _('verifier model'), max_length=100, blank=True,
        help_text=_('Model for the verifier step only, e.g. gpt-4o. Empty: the chat model.'),
    )

    class Meta(BaseModel.Meta):
        verbose_name = _('AI settings')
        verbose_name_plural = _('AI settings')

    def __str__(self):
        return f'{self.chat_model} ({self.temperature})'

    def save(self, *args, **kwargs):
        self.pk = 1  # only one row
        if self.created_at is None:
            # Saving a new instance over the existing row is an UPDATE, where
            # auto_now_add does not apply: keep the row's creation date.
            existing = AISettings.objects.filter(pk=1).values_list('created_at', flat=True).first()
            if existing is not None:
                self.created_at = existing
                self._state.adding = False
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        """Return the settings row, creating it with defaults if missing."""
        settings, _created = cls.objects.get_or_create(pk=1)
        return settings
