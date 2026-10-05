"""Tests for telegram_bot/services.py and receivers.py: notices to specialists and their log (ADR 0022, 0023)."""

from unittest import mock

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from core.tests.support import make_center, make_interaction, make_membership, make_question, make_referral, make_user
from qa.models import Referral
from qa.services import open_referral
from telegram_bot.models import TelegramMessage
from telegram_bot.services import QUESTION_MAX, notify_referral, referral_notice, resend
from telegram_bot.tests.support import FakeClient

GROUP = -1001234567890
SPECIALIST = 111


class NoticeTests(TestCase):
    """What a specialist reads: in a given language, escaped, without the asker, with the live line or 🎫."""

    def referral(self, text='Can I pray <sitting>?', lang='en', mode=Referral.Mode.LIVE, **fields):
        question = make_question(text=text, lang=lang, **fields)
        return make_referral(question=make_interaction(question=question, decision='refer').question, mode=mode)

    def test_in_the_given_language_with_reason_language_and_follow_up_number(self):
        referral = self.referral()
        notice = referral_notice(referral, 'fr')
        for expected in ('Motif', 'Non couverte par les sources', 'Anglais', f'<code>{referral.question.uuid}</code>'):
            self.assertIn(expected, notice)

    def test_question_is_escaped_and_the_asker_never_shown(self):
        notice = referral_notice(self.referral(asker=make_user(email='asker@example.com')), 'en')
        self.assertIn('<blockquote>Can I pray &lt;sitting&gt;?</blockquote>', notice)
        self.assertNotIn('asker@example.com', notice)

    def test_long_question_is_cut(self):
        notice = referral_notice(self.referral(text='x' * (QUESTION_MAX + 50)), 'en')
        self.assertIn('x' * QUESTION_MAX + '…', notice)
        self.assertNotIn('x' * (QUESTION_MAX + 1), notice)

    @override_settings(REFERRAL_LIVE_SECONDS=60)
    def test_live_window_or_ticket_line(self):
        self.assertIn('⏱ Answer within 1 minute', referral_notice(self.referral(), 'en'))
        self.assertIn('🎫 Ticket', referral_notice(self.referral(mode=Referral.Mode.TICKET), 'en'))


class NotifyTests(TestCase):
    """``notify_referral`` reaches linked specialists privately (and the group); every attempt is logged."""

    def setUp(self):
        self.center = make_center(languages=['ar'])
        self.referral = make_referral(center=self.center)
        self.specialist = make_membership(center=self.center, user=make_user(
            telegram_chat_id=SPECIALIST, preferred_lang='fr')).user

    def test_linked_specialists_get_a_private_notice_with_the_answer_button(self):
        make_membership(center=self.center, user=make_user())  # not linked: nothing sent
        client = FakeClient()
        [message] = notify_referral(self.referral, client)
        self.assertEqual((message.chat_id, message.status, message.message_id),
                         (SPECIALIST, TelegramMessage.Status.SENT, 101))
        self.assertIn('Nouvelle question', client.sent[0][1])  # the specialist's own language
        button = client.markups[0]['inline_keyboard'][0][0]
        self.assertEqual(button['callback_data'], f'answer:{self.referral.question.uuid}')

    def test_a_connected_group_also_gets_it_in_the_center_language(self):
        self.center.telegram_chat_id = GROUP
        self.center.save(update_fields=['telegram_chat_id', 'updated_at'])
        client = FakeClient()
        notify_referral(self.referral, client)
        self.assertEqual([chat for chat, _text in client.sent], [SPECIALIST, GROUP])
        self.assertIn('سؤال جديد', client.sent[1][1])

    def test_former_members_and_deactivated_accounts_get_nothing(self):
        self.specialist.memberships.update(is_active=False, left_at=self.referral.created_at,
                                           updated_at=self.referral.created_at)
        self.assertEqual(notify_referral(self.referral, FakeClient()), [])

    def test_failed_notice_is_logged_not_raised(self):
        with self.assertLogs('telegram_bot.services', 'WARNING'):
            [message] = notify_referral(self.referral, FakeClient(error='sendMessage: 403 Forbidden: bot was blocked'))
        self.assertEqual((message.status, message.error),
                         (TelegramMessage.Status.FAILED, 'sendMessage: 403 Forbidden: bot was blocked'))

    def test_nothing_sent_without_token(self):
        self.assertEqual(notify_referral(self.referral, FakeClient(enabled=False)), [])
        self.assertFalse(TelegramMessage.objects.exists())

    def test_resend_to_the_same_chat_and_refusals(self):
        with self.assertLogs('telegram_bot.services', 'WARNING'):
            [failed] = notify_referral(self.referral, FakeClient(error='sendMessage: Timeout'))
        attempt = resend(failed, FakeClient())
        self.assertEqual((attempt.chat_id, attempt.status), (SPECIALIST, TelegramMessage.Status.SENT))
        for message, client, code in ((attempt, FakeClient(), 'telegram_not_failed'),
                                      (failed, FakeClient(enabled=False), 'telegram_unavailable')):
            with self.subTest(code=code), self.assertRaises(ValidationError) as caught:
                resend(message, client)
            self.assertEqual(caught.exception.code, code)


class ReceiverTests(TestCase):
    """Opening a referral notifies the specialists once the transaction commits."""

    def test_open_referral_notifies_after_commit(self):
        question = make_interaction(decision='refer').question
        with mock.patch('telegram_bot.receivers.notify_referral') as notify:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                referral = open_referral(question, Referral.Reason.LEVEL_D)
            notify.assert_not_called()
            for callback in callbacks:
                callback()
        notify.assert_called_once_with(referral)

    def test_a_failing_notice_never_reaches_the_asker(self):
        question = make_interaction(decision='refer').question
        with mock.patch('telegram_bot.receivers.notify_referral', side_effect=RuntimeError('database gone')), \
                self.assertLogs('telegram_bot.receivers', 'ERROR'), self.captureOnCommitCallbacks(execute=True):
            open_referral(question, Referral.Reason.NO_EVIDENCE)
        self.assertTrue(Referral.objects.filter(question=question).exists())
