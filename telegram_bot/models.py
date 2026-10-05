"""
The log of messages the bot sent, and the codes that link Telegram accounts (ADR 0022).

One ``TelegramMessage`` per attempt, sent or failed, so a failure is visible and
can be sent again; its ``message_id`` matches a specialist's reply in the group
to its referral. A ``TelegramLinkCode`` is a one-time code in a
``t.me/<bot>?start=<code>`` link: opening it links that Telegram account to the
user; with a ``center``, it is a ``t.me/<bot>?startgroup=<code>`` link that
connects the group the bot is added to (ADR 0023).
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
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


class TelegramLinkCodeQuerySet(models.QuerySet):
    """Link codes still usable: not used and not expired."""

    def usable(self):
        """Codes neither used nor expired."""
        return self.filter(used_at__isnull=True, expires_at__gt=timezone.now())


class TelegramLinkCode(BaseModel):
    """
    A one-time code that links a Telegram account to ``user``, or, with a
    ``center``, connects a Telegram group to that center (ADR 0023).

    Only the SHA-256 of the code is stored: the code itself is shown once, in the
    link, and cannot be read back from the database.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='telegram_link_codes',
        verbose_name=_('user'),
    )
    # Set for a group connection code; empty for a personal link code
    center = models.ForeignKey(
        'core.Center', on_delete=models.CASCADE, null=True, blank=True, related_name='+',
        verbose_name=_('center'),
    )
    code_hash = models.CharField(_('code hash'), max_length=64, unique=True)
    expires_at = models.DateTimeField(_('expires at'))
    used_at = models.DateTimeField(_('used at'), null=True, blank=True)

    objects = TelegramLinkCodeQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        verbose_name = _('Telegram link code')
        verbose_name_plural = _('Telegram link codes')

    def __str__(self):
        return f'{self.user} ({self.expires_at:%Y-%m-%d %H:%M})'
