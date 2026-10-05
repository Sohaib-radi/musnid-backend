"""Tests for centers/<slug>/telegram/, connect/ and disconnect/: a center's group (ADR 0023)."""

from unittest import mock

from django.utils import timezone

from api.tests.base import APITestCase
from core.models import Center, Membership
from core.tests.support import make_center, make_membership
from telegram_bot.client import TelegramError
from telegram_bot.tests.support import FakeClient


class TelegramConnectAPITests(APITestCase):
    """The admin gets a startgroup link; any member polls the status."""

    def setUp(self):
        super().setUp()
        self.center = make_center(slug='dar')
        self.admin = make_membership(center=self.center, role=Membership.Role.CENTER_ADMIN).user
        self.specialist = make_membership(center=self.center).user

    def connect(self, client=None):
        with mock.patch('api.v1.views.telegram.TelegramClient', return_value=client or FakeClient()):
            return self.client.post(self.url('center-telegram-connect', 'dar'))

    def test_admin_gets_a_one_time_startgroup_link(self):
        self.authenticate(self.admin)
        response = self.connect()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data['url'].startswith('https://t.me/musnid_test_bot?startgroup='))
        self.assertGreater(response.data['expires_at'], timezone.now().isoformat())

    def test_specialist_and_non_operational_center_are_refused(self):
        self.authenticate(self.specialist)
        self.assertError(self.connect(), 403, 'not_center_admin')
        Center.objects.filter(pk=self.center.pk).update(is_active=False, updated_at=timezone.now())
        self.authenticate(self.admin)
        self.assertError(self.connect(), 403, 'center_not_operational')

    def test_bot_off_or_telegram_down_is_503(self):
        self.authenticate(self.admin)
        self.assertError(self.connect(FakeClient(enabled=False)), 503, 'telegram_unavailable')
        broken = FakeClient()
        broken.username = mock.Mock(side_effect=TelegramError('getMe: ConnectError'))
        self.assertError(self.connect(broken), 503, 'telegram_unavailable')

    def test_status_for_members(self):
        self.authenticate(self.specialist)
        self.assertEqual(self.client.get(self.url('center-telegram', 'dar')).data,
                         {'connected': False, 'me_linked': False})
        Center.objects.filter(pk=self.center.pk).update(telegram_chat_id=-100, updated_at=timezone.now())
        self.specialist.telegram_chat_id = 42
        self.specialist.save(update_fields=['telegram_chat_id', 'updated_at'])
        self.assertEqual(self.client.get(self.url('center-telegram', 'dar')).data,
                         {'connected': True, 'me_linked': True})

    def test_status_for_non_members_is_404(self):
        self.authenticate()
        self.assertError(self.client.get(self.url('center-telegram', 'dar')), 404, 'not_found')

    def test_admin_disconnects(self):
        Center.objects.filter(pk=self.center.pk).update(telegram_chat_id=-100, updated_at=timezone.now())
        self.authenticate(self.admin)
        with mock.patch('telegram_bot.linking.TelegramClient', return_value=FakeClient()), \
                self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url('center-telegram-disconnect', 'dar'))
        self.assertEqual(response.data, {'connected': False, 'me_linked': False})
        self.center.refresh_from_db()
        self.assertIsNone(self.center.telegram_chat_id)

    def test_specialist_cannot_disconnect(self):
        self.authenticate(self.specialist)
        self.assertError(self.client.post(self.url('center-telegram-disconnect', 'dar')), 403, 'not_center_admin')

