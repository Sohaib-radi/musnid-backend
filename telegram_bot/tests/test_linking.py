"""Tests for telegram_bot/linking.py: one-time links for Telegram accounts and center groups (ADR 0023)."""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from core.models import Center, Membership
from core.tests.support import make_center, make_membership, make_user
from telegram_bot.linking import (
    LINK_MINUTES, code_hash, connect_group, create_group_link, create_link, disconnect_center, disconnect_group,
    link_account, move_group,
)
from telegram_bot.models import TelegramLinkCode
from telegram_bot.tests.support import FakeClient

TELEGRAM_ID = 987654321
GROUP = -1001234567890


def code_of(url):
    return url.rsplit('=', 1)[1]


class LinkingTests(TestCase):
    """``create_link`` and ``link_account``: hashed, one-time, expiring codes."""

    def setUp(self):
        self.user = make_user()

    def assertRefused(self, code, *arguments):
        with self.assertRaises(ValidationError) as caught:
            link_account(*arguments)
        self.assertEqual(caught.exception.code, code)

    def test_link_points_to_the_bot_and_stores_only_the_hash(self):
        url, expires_at = create_link(self.user, FakeClient())
        self.assertTrue(url.startswith('https://t.me/musnid_test_bot?start='))
        code = code_of(url)
        self.assertRegex(code, r'^[A-Za-z0-9_-]{22}$')
        row = TelegramLinkCode.objects.get()
        self.assertEqual(row.code_hash, code_hash(code))
        self.assertNotIn(code, str(TelegramLinkCode.objects.values().get()))
        self.assertAlmostEqual(expires_at, timezone.now() + timedelta(minutes=LINK_MINUTES),
                               delta=timedelta(seconds=5))

    def test_opening_the_link_links_the_account_once(self):
        code = code_of(create_link(self.user, FakeClient())[0])
        self.assertEqual(link_account(code, TELEGRAM_ID), self.user)
        self.user.refresh_from_db()
        self.assertEqual(self.user.telegram_chat_id, TELEGRAM_ID)
        self.assertRefused('telegram_link_invalid', code, TELEGRAM_ID)

    def test_expired_unknown_and_deactivated_links_are_refused(self):
        code = code_of(create_link(self.user, FakeClient())[0])
        TelegramLinkCode.objects.update(expires_at=timezone.now(), updated_at=timezone.now())
        self.assertRefused('telegram_link_invalid', code, TELEGRAM_ID)
        self.assertRefused('telegram_link_invalid', 'unknown-code', TELEGRAM_ID)
        inactive = make_user(is_active=False)
        with self.assertRaises(ValidationError) as caught:
            create_link(inactive, FakeClient())
        self.assertEqual(caught.exception.code, 'telegram_link_inactive_user')

    def test_a_telegram_account_links_one_user_only(self):
        make_user(telegram_chat_id=TELEGRAM_ID)
        code = code_of(create_link(self.user, FakeClient())[0])
        self.assertRefused('telegram_already_linked', code, TELEGRAM_ID)

    def test_linking_again_replaces_the_telegram_account(self):
        link_account(code_of(create_link(self.user, FakeClient())[0]), TELEGRAM_ID)
        link_account(code_of(create_link(self.user, FakeClient())[0]), TELEGRAM_ID + 1)
        self.user.refresh_from_db()
        self.assertEqual(self.user.telegram_chat_id, TELEGRAM_ID + 1)


class GroupConnectionTests(TestCase):
    """``create_group_link`` and ``connect_group``: one group per center, linked by its admin."""

    def setUp(self):
        self.center = make_center()
        self.admin = make_membership(center=self.center, role=Membership.Role.CENTER_ADMIN).user

    def code(self):
        url, _expires_at = create_group_link(self.center, self.admin, FakeClient())
        self.assertIn('?startgroup=', url)
        return code_of(url)

    def test_adding_the_bot_connects_the_group_and_links_the_admin(self):
        self.assertEqual(connect_group(self.code(), GROUP, TELEGRAM_ID), self.center)
        self.center.refresh_from_db()
        self.admin.refresh_from_db()
        self.assertEqual((self.center.telegram_chat_id, self.admin.telegram_chat_id), (GROUP, TELEGRAM_ID))

    def test_only_center_admins_of_operational_centers(self):
        specialist = make_membership(center=self.center).user
        with self.assertRaises(ValidationError) as caught:
            create_group_link(self.center, specialist, FakeClient())
        self.assertEqual(caught.exception.code, 'telegram_not_center_admin')
        code = self.code()
        Center.objects.filter(pk=self.center.pk).update(is_active=False, updated_at=timezone.now())
        with self.assertRaises(ValidationError) as caught:
            connect_group(code, GROUP, TELEGRAM_ID)
        self.assertEqual(caught.exception.code, 'telegram_link_invalid')

    def test_a_group_serves_one_center(self):
        make_center(telegram_chat_id=GROUP)
        with self.assertRaises(ValidationError) as caught:
            connect_group(self.code(), GROUP, TELEGRAM_ID)
        self.assertEqual(caught.exception.code, 'telegram_group_taken')

    def test_codes_are_not_interchangeable(self):
        group_code = self.code()
        personal_code = code_of(create_link(self.admin, FakeClient())[0])
        with self.assertRaises(ValidationError):
            link_account(group_code, TELEGRAM_ID)
        with self.assertRaises(ValidationError):
            connect_group(personal_code, GROUP, TELEGRAM_ID)

    def test_an_admin_linked_elsewhere_is_not_relinked(self):
        make_user(telegram_chat_id=TELEGRAM_ID)
        connect_group(self.code(), GROUP, TELEGRAM_ID)
        self.admin.refresh_from_db()
        self.assertIsNone(self.admin.telegram_chat_id)

    def test_disconnect_and_move(self):
        connect_group(self.code(), GROUP, TELEGRAM_ID)
        self.assertEqual(move_group(GROUP, GROUP - 1), 1)
        self.center.refresh_from_db()
        self.assertEqual(self.center.telegram_chat_id, GROUP - 1)
        self.assertEqual(disconnect_group(GROUP - 1), 1)
        self.center.refresh_from_db()
        self.assertIsNone(self.center.telegram_chat_id)


class DisconnectCenterTests(TestCase):
    """``disconnect_center``: the admin disconnects; the bot says goodbye and leaves, best effort."""

    def setUp(self):
        self.center = make_center(telegram_chat_id=GROUP, languages=['en'])
        self.admin = make_membership(center=self.center, role=Membership.Role.CENTER_ADMIN).user

    def test_clears_the_group_then_says_goodbye_and_leaves(self):
        client = FakeClient()
        with self.captureOnCommitCallbacks(execute=True):
            disconnect_center(self.center, self.admin, client)
        self.center.refresh_from_db()
        self.assertIsNone(self.center.telegram_chat_id)
        self.assertIn('no longer connected', client.sent[0][1])
        self.assertEqual(client.left, [GROUP])

    def test_telegram_failure_still_disconnects(self):
        with self.assertLogs('telegram_bot.linking', 'WARNING'), self.captureOnCommitCallbacks(execute=True):
            disconnect_center(self.center, self.admin, FakeClient(error='leaveChat: 400 Bad Request'))
        self.center.refresh_from_db()
        self.assertIsNone(self.center.telegram_chat_id)

    def test_specialists_refused_and_no_group_is_a_no_op(self):
        specialist = make_membership(center=self.center).user
        with self.assertRaises(ValidationError) as caught:
            disconnect_center(self.center, specialist, FakeClient())
        self.assertEqual(caught.exception.code, 'telegram_not_center_admin')
        client = FakeClient()
        with self.captureOnCommitCallbacks(execute=True):
            disconnect_center(self.center, self.admin, client)
            disconnect_center(self.center, self.admin, client)
        self.assertEqual(client.left, [GROUP])

