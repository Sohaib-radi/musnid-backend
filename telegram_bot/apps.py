"""Application configuration for the ``telegram_bot`` app."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class TelegramBotConfig(AppConfig):
    """Registers the ``telegram_bot`` app: the Telegram channel of the centers (ADR 0022)."""

    name = 'telegram_bot'
    verbose_name = _('Telegram bot')

    def ready(self):
        """Connect the receivers: ``qa`` announces referrals without knowing about Telegram."""
        from telegram_bot import receivers  # noqa: F401
