"""
Receive Telegram updates by long polling and handle them (ADR 0023).

For local development, where Telegram cannot reach the webhook. Runs until
Ctrl+C. Network hiccups and Telegram's own errors are retried after
``RETRY_SECONDS``; a refusal (wrong token, a webhook in the way) stops it.
"""

import logging
import time

from django.core.management.base import BaseCommand, CommandError

from telegram_bot.client import TelegramClient, TelegramError
from telegram_bot.updates import handle_update

logger = logging.getLogger(__name__)

#: Seconds Telegram holds each request open while no update arrives
WAIT = 25
#: Seconds to wait before polling again after a failure that may pass by itself
RETRY_SECONDS = 5


class Command(BaseCommand):
    help = 'Receive Telegram updates by long polling (local development); Ctrl+C to stop.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Handle the pending updates once, then stop.')

    def handle(self, *args, **options):
        client = TelegramClient()
        if not client.enabled:
            raise CommandError('TELEGRAM_BOT_TOKEN is not set.')
        self.stdout.write('Polling Telegram; Ctrl+C to stop.')
        offset = None
        try:
            while True:
                try:
                    updates = client.get_updates(offset=offset, wait=0 if options['once'] else WAIT)
                except TelegramError as error:
                    if options['once'] or not error.retryable:
                        raise CommandError(str(error)) from None
                    logger.warning('Telegram polling failed, retrying in %s s: %s', RETRY_SECONDS, error)
                    time.sleep(RETRY_SECONDS)
                    continue
                for update in updates:
                    offset = update['update_id'] + 1
                    try:
                        outcome = handle_update(update, client)
                    except Exception:  # one bad update must not stop the bot
                        logger.exception('Telegram update %s failed', update['update_id'])
                        continue
                    if outcome:
                        self.stdout.write(f'update {update["update_id"]}: {outcome}')
                if options['once']:
                    if offset is not None:
                        client.get_updates(offset=offset)  # confirm the handled updates
                    return
        except KeyboardInterrupt:
            self.stdout.write('Stopped.')
