"""
The log of messages the bot sent (ADR 0022).

One row per attempt, sent or failed, so a failure is visible and can be sent
again. ``message_id`` will let a specialist's reply in the group be matched to
its referral.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import BaseModel
from qa.models import Referral


class TelegramMessage(BaseModel):
    """A message the bot sent, or tried to send, about a referral."""

    class Kind(models.TextChoices):
        """What the message is for."""

        REFERRAL_NOTICE = 'referral_notice', _('New referral notice')

    class Status(models.TextChoices):
        """Whether Telegram accepted the message."""

        SENT = 'sent', _('Sent')
        FAILED = 'failed', _('Failed')

    referral = models.ForeignKey(
        Referral, on_delete=models.CASCADE, related_name='telegram_messages', verbose_name=_('referral'),
    )
    kind = models.CharField(_('kind'), max_length=20, choices=Kind.choices)
    chat_id = models.BigIntegerField(_('chat ID'))
    message_id = models.BigIntegerField(_('message ID'), null=True, blank=True)
    status = models.CharField(_('status'), max_length=10, choices=Status.choices)
    text = models.TextField(_('text'))
    error = models.TextField(_('error'), blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = _('Telegram message')
        verbose_name_plural = _('Telegram messages')
        indexes = [models.Index(fields=['chat_id', 'message_id'], name='telegram_message_lookup')]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(status='sent') | models.Q(message_id__isnull=False),
                name='telegram_sent_has_message_id',
                violation_error_message=_('A sent Telegram message needs its message ID.'),
            ),
        ]

    def __str__(self):
        return f'{self.get_kind_display()} ({self.get_status_display()})'
