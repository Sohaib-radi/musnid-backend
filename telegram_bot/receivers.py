"""Receivers of ``qa`` signals, connected in ``TelegramBotConfig.ready`` (ADR 0022)."""

import logging

from django.dispatch import receiver

from qa.signals import referral_opened
from telegram_bot.services import notify_referral

logger = logging.getLogger(__name__)


@receiver(referral_opened, dispatch_uid='telegram_bot.notify_center')
def notify_center(sender, referral, **kwargs):
    """Post the new referral to its center's group; any failure is logged, never raised to the asker."""
    try:
        notify_referral(referral)
    except Exception:  # the question is saved; a notice problem must not turn the answer into an error
        logger.exception('Telegram notice of referral %s could not be sent', referral.pk)
