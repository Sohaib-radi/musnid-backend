"""Receivers of ``qa`` signals, connected in ``TelegramBotConfig.ready`` (ADR 0022)."""

import logging

from django.dispatch import receiver

from qa.signals import referral_answered, referral_opened
from telegram_bot.services import mark_answered, notify_referral

logger = logging.getLogger(__name__)


@receiver(referral_opened, dispatch_uid='telegram_bot.notify_center')
def notify_center(sender, referral, **kwargs):
    """Post the new referral to its center's group; any failure is logged, never raised to the asker."""
    try:
        notify_referral(referral)
    except Exception:  # the question is saved; a notice problem must not turn the answer into an error
        logger.exception('Telegram notice of referral %s could not be sent', referral.pk)


@receiver(referral_answered, dispatch_uid='telegram_bot.close_for_others')
def close_for_others(sender, referral, author, **kwargs):
    """Mark the referral's notices answered for every specialist; failures are logged, never raised."""
    try:
        mark_answered(referral, author)
    except Exception:  # the answer is saved; a Telegram problem must not undo it
        logger.exception('Marking referral %s answered in Telegram failed', referral.pk)

