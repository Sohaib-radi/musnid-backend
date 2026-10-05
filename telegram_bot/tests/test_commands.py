"""Tests for the telegram_chats, telegram_poll and telegram_webhook commands (ADR 0022, ADR 0023)."""

from io import StringIO
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, override_settings

from telegram_bot.client import TelegramError
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


@override_settings(TELEGRAM_BOT_TOKEN='123:abc')
class TelegramPollTests(SimpleTestCase):
    """``--once`` handles the pending updates, confirms them, and survives a failing one."""

    def test_once_handles_and_confirms(self):
        out = StringIO()
        with mock.patch('telegram_bot.client.TelegramClient.get_updates', side_effect=[UPDATES, []]) as updates, \
                mock.patch('telegram_bot.management.commands.telegram_poll.handle_update',
                           side_effect=['linked', RuntimeError('boom'), None]) as handle, \
                self.assertLogs('telegram_bot.management.commands.telegram_poll', 'ERROR'):
            call_command('telegram_poll', '--once', stdout=out)
        self.assertEqual(handle.call_count, 3)
        self.assertIn('update 1: linked', out.getvalue())
        self.assertEqual(updates.call_args_list[1], mock.call(offset=4))

    @override_settings(TELEGRAM_BOT_TOKEN='')
    def test_refuses_without_token(self):
        with self.assertRaisesMessage(CommandError, 'TELEGRAM_BOT_TOKEN is not set.'):
            call_command('telegram_poll', '--once')

    def test_network_errors_are_retried_and_refusals_stop(self):
        failures = [TelegramError('getUpdates: ReadTimeout', retryable=True),
                    TelegramError('getUpdates: 409 Conflict: terminated by setWebhook')]
        with mock.patch('telegram_bot.client.TelegramClient.get_updates', side_effect=failures), \
                mock.patch('telegram_bot.management.commands.telegram_poll.time.sleep') as sleep, \
                self.assertLogs('telegram_bot.management.commands.telegram_poll', 'WARNING'), \
                self.assertRaisesMessage(CommandError, 'getUpdates: 409 Conflict'):
            call_command('telegram_poll', stdout=StringIO())
        sleep.assert_called_once_with(5)


@override_settings(TELEGRAM_BOT_TOKEN='123:abc', TELEGRAM_WEBHOOK_SECRET='s3cret', SITE_URL='https://api.musnid.online')
class TelegramWebhookCommandTests(SimpleTestCase):
    """``--set`` needs an https site and a secret; ``--delete`` removes the webhook."""

    def test_set_registers_the_url_and_secret(self):
        out = StringIO()
        with mock.patch('telegram_bot.client.TelegramClient.call') as call:
            call_command('telegram_webhook', '--set', stdout=out)
        call.assert_called_once_with('setWebhook', url='https://api.musnid.online/telegram/webhook/',
                                     secret_token='s3cret', allowed_updates=['message', 'my_chat_member'])
        self.assertNotIn('s3cret', out.getvalue())

    @override_settings(SITE_URL='http://localhost:8000')
    def test_set_refuses_without_https(self):
        with self.assertRaisesMessage(CommandError, 'Set DJANGO_SITE_URL (https) and TELEGRAM_WEBHOOK_SECRET first.'):
            call_command('telegram_webhook', '--set')

    def test_delete(self):
        with mock.patch('telegram_bot.client.TelegramClient.call') as call:
            call_command('telegram_webhook', '--delete', stdout=StringIO())
        call.assert_called_once_with('deleteWebhook')

