"""Tests for telegram_bot/admin.py: the read-only message log and "Send again" (ADR 0022)."""

from unittest import mock

from django.urls import reverse

from core.tests.support import make_center, make_referral
from core.tests.test_admin import AdminTestCase
from telegram_bot.models import TelegramMessage
from telegram_bot.tests.support import FakeClient


class TelegramMessageAdminTests(AdminTestCase):
    """List, read-only pages, and resending failed messages."""

    def setUp(self):
        super().setUp()
        referral = make_referral(center=make_center(telegram_chat_id=-100))
        self.failed = TelegramMessage.objects.create(
            referral=referral, kind=TelegramMessage.Kind.REFERRAL_NOTICE, chat_id=-100,
            status=TelegramMessage.Status.FAILED, text='Notice', error='sendMessage: 400 Bad Request: chat not found')

    def send_again(self, messages):
        return self.client.post(reverse('admin:telegram_bot_telegrammessage_changelist'), {
            'action': 'send_again', '_selected_action': [message.pk for message in messages]}, follow=True)

    def test_list_shows_status_and_error(self):
        response = self.client.get(reverse('admin:telegram_bot_telegrammessage_changelist'))
        self.assertContains(response, 'Failed')
        self.assertContains(response, 'chat not found')

    def test_read_only(self):
        self.assertEqual(self.client.get(reverse('admin:telegram_bot_telegrammessage_add')).status_code, 403)
        page = self.client.get(reverse('admin:telegram_bot_telegrammessage_change', args=[self.failed.pk]))
        self.assertNotContains(page, 'name="_save"')
        self.assertContains(page, reverse('admin:qa_referral_change', args=[self.failed.referral_id]))

    def test_send_again(self):
        with mock.patch('telegram_bot.services.TelegramClient', return_value=FakeClient()):
            response = self.send_again([self.failed])
        self.assertEqual(self.messages(response), ['1 message was sent.'])
        self.assertTrue(TelegramMessage.objects.filter(status=TelegramMessage.Status.SENT).exists())

    def test_send_again_reports_refusals(self):
        response = self.send_again([self.failed])  # tests run without a token
        self.assertIn('The bot has no token, or the center has no Telegram group.', self.messages(response)[0])
