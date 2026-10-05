"""
List the chats the bot was added to, with their IDs, to fill ``Center.telegram_chat_id``.

Reads ``getUpdates``: add the bot to the group and send a message there first.
Works only while no webhook is set. Never prints the token.
"""

from django.core.management.base import BaseCommand, CommandError

from telegram_bot.client import TelegramClient, TelegramError


def chats_in(updates):
    """The distinct chats found in ``updates`` (messages and membership changes), as ``{id: (type, title)}``."""
    chats = {}
    for update in updates:
        for key in ('message', 'my_chat_member'):
            chat = (update.get(key) or {}).get('chat')
            if chat:
                chats[chat['id']] = (chat.get('type', ''), chat.get('title') or chat.get('username') or '')
    return chats


class Command(BaseCommand):
    help = 'List the chats the bot was added to (ID, type, title), from pending updates.'

    def handle(self, *args, **options):
        client = TelegramClient()
        if not client.enabled:
            raise CommandError('TELEGRAM_BOT_TOKEN is not set.')
        try:
            chats = chats_in(client.get_updates())
        except TelegramError as error:
            raise CommandError(str(error)) from None
        if not chats:
            self.stdout.write('No chat found: add the bot to the group, send a message there, and run again.')
        for chat_id, (kind, title) in chats.items():
            self.stdout.write(f'{chat_id}\t{kind}\t{title}')
