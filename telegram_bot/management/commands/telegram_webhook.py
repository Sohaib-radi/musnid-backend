"""
Register or remove the production webhook with Telegram (ADR 0023).

``--set`` points Telegram at ``DJANGO_SITE_URL/telegram/webhook/`` with
``TELEGRAM_WEBHOOK_SECRET``; ``--delete`` removes it, so ``telegram_poll`` can
run. Never prints the token or the secret.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse

from telegram_bot.client import TelegramClient, TelegramError


class Command(BaseCommand):
    help = 'Register (--set) or remove (--delete) the Telegram webhook.'

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--set', action='store_true', help='Point Telegram at DJANGO_SITE_URL/telegram/webhook/.')
        group.add_argument('--delete', action='store_true', help='Remove the webhook (to use telegram_poll).')

    def handle(self, *args, **options):
        client = TelegramClient()
        if not client.enabled:
            raise CommandError('TELEGRAM_BOT_TOKEN is not set.')
        try:
            if options['delete']:
                client.call('deleteWebhook')
                self.stdout.write('Webhook removed.')
                return
            if not settings.SITE_URL.startswith('https://') or not settings.TELEGRAM_WEBHOOK_SECRET:
                raise CommandError('Set DJANGO_SITE_URL (https) and TELEGRAM_WEBHOOK_SECRET first.')
            url = settings.SITE_URL + reverse('telegram_bot:webhook')
            client.call('setWebhook', url=url, secret_token=settings.TELEGRAM_WEBHOOK_SECRET,
                        allowed_updates=['message', 'my_chat_member'])
            self.stdout.write(f'Webhook set to {url}.')
        except TelegramError as error:
            raise CommandError(str(error)) from None
