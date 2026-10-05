"""Tests for telegram_bot/views.py: the webhook answers only Telegram, with the secret (ADR 0023)."""

from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

SECRET = 'webhook-secret_123'
UPDATE = {'update_id': 5, 'message': {'message_id': 1, 'chat': {'id': 1, 'type': 'private'}, 'text': 'hi'}}


@override_settings(TELEGRAM_WEBHOOK_SECRET=SECRET)
class WebhookTests(TestCase):
    """404 without the secret, 400 for unreadable bodies, 200 once handled (even on failure)."""

    def post(self, body=UPDATE, secret=SECRET, **extra):
        headers = {'X-Telegram-Bot-Api-Secret-Token': secret} if secret is not None else {}
        return self.client.post(reverse('telegram_bot:webhook'), body, content_type='application/json',
                                headers=headers, **extra)

    @mock.patch('telegram_bot.views.handle_update')
    def test_update_with_the_secret_is_handled(self, handle):
        self.assertEqual(self.post().status_code, 200)
        handle.assert_called_once_with(UPDATE)

    @mock.patch('telegram_bot.views.handle_update')
    def test_missing_or_wrong_secret_is_404(self, handle):
        self.assertEqual(self.post(secret=None).status_code, 404)
        self.assertEqual(self.post(secret='wrong').status_code, 404)
        with override_settings(TELEGRAM_WEBHOOK_SECRET=''):
            self.assertEqual(self.post(secret='').status_code, 404)
        handle.assert_not_called()

    def test_unreadable_body_and_get(self):
        self.assertEqual(self.post(body='not json').status_code, 400)
        self.assertEqual(self.client.get(reverse('telegram_bot:webhook')).status_code, 405)

    @mock.patch('telegram_bot.views.handle_update', side_effect=RuntimeError('boom'))
    def test_failed_update_still_answers_200(self, handle):
        with self.assertLogs('telegram_bot.views', 'ERROR'):
            self.assertEqual(self.post().status_code, 200)
