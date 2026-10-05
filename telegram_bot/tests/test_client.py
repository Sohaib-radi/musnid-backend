"""Tests for telegram_bot/client.py: Bot API calls, errors, and the token never shown (ADR 0022)."""

import json

import httpx
from django.test import SimpleTestCase, override_settings

from telegram_bot.client import TelegramClient, TelegramError

TOKEN = '123456:secret-token-value'


def client_replying(reply=None, error=None, requests=None):
    """A client whose transport answers ``reply`` (JSON) or raises ``error``, recording each request."""
    def handle(request):
        if requests is not None:
            requests.append(request)
        if error:
            raise error
        return httpx.Response(200, json=reply)
    return TelegramClient(token=TOKEN, transport=httpx.MockTransport(handle))


class TelegramClientTests(SimpleTestCase):
    """``call`` returns ``result`` or raises ``TelegramError`` without the token."""

    def test_send_message_posts_html_without_previews(self):
        requests = []
        result = client_replying({'ok': True, 'result': {'message_id': 7}}, requests=requests).send_message(-100, 'Hi')
        self.assertEqual(result, {'message_id': 7})
        self.assertEqual(requests[0].url.path, f'/bot{TOKEN}/sendMessage')
        self.assertEqual(json.loads(requests[0].content), {
            'chat_id': -100, 'text': 'Hi', 'parse_mode': 'HTML', 'link_preview_options': {'is_disabled': True}})

    def test_telegram_refusal_keeps_its_description(self):
        client = client_replying({'ok': False, 'error_code': 400, 'description': 'Bad Request: chat not found'})
        with self.assertRaisesMessage(TelegramError, 'sendMessage: 400 Bad Request: chat not found'):
            client.send_message(-100, 'Hi')

    def test_network_failure_never_shows_the_token(self):
        error = httpx.ConnectError(f'cannot reach https://api.telegram.org/bot{TOKEN}/sendMessage')
        with self.assertRaises(TelegramError) as caught:
            client_replying(error=error).send_message(-100, 'Hi')
        self.assertEqual(str(caught.exception), 'sendMessage: ConnectError')
        self.assertIsNone(caught.exception.__cause__)
        self.assertTrue(caught.exception.__suppress_context__)

    def test_unreadable_reply(self):
        client = TelegramClient(token=TOKEN, transport=httpx.MockTransport(lambda request: httpx.Response(502)))
        with self.assertRaisesMessage(TelegramError, 'getUpdates: JSONDecodeError'):
            client.get_updates()

    @override_settings(TELEGRAM_BOT_TOKEN='')
    def test_empty_token_disables_the_bot_and_repr_hides_the_token(self):
        self.assertFalse(TelegramClient().enabled)
        self.assertNotIn(TOKEN, repr(TelegramClient(token=TOKEN)))
