"""Tests for the telegram_chats command: chat IDs from pending updates, never the token (ADR 0022)."""

from io import StringIO
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, override_settings

from telegram_bot.management.commands.telegram_chats import chats_in

UPDATES = [
    {'update_id': 1, 'my_chat_member': {'chat': {'id': -100123, 'type': 'supergroup', 'title': 'Center group'}}},
    {'update_id': 2, 'message': {'chat': {'id': -100123, 'type': 'supergroup', 'title': 'Center group'}}},
    {'update_id': 3, 'message': {'chat': {'id': 42, 'type': 'private', 'username': 'specialist'}}},
]


class TelegramChatsTests(SimpleTestCase):
    """Distinct chats, a clear message without token, no chat found."""

    def test_chats_in_updates(self):
        self.assertEqual(chats_in(UPDATES), {-100123: ('supergroup', 'Center group'), 42: ('private', 'specialist')})

    @override_settings(TELEGRAM_BOT_TOKEN='123:abc')
    def test_lists_each_chat_once(self):
        out = StringIO()
        with mock.patch('telegram_bot.client.TelegramClient.get_updates', return_value=UPDATES):
            call_command('telegram_chats', stdout=out)
        self.assertEqual(out.getvalue().splitlines(), ['-100123\tsupergroup\tCenter group', '42\tprivate\tspecialist'])
        self.assertNotIn('123:abc', out.getvalue())

    def test_refuses_without_token(self):
        with self.assertRaisesMessage(CommandError, 'TELEGRAM_BOT_TOKEN is not set.'):
            call_command('telegram_chats')
