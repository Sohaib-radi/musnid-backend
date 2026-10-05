"""Tests for telegram_bot/services.py and receivers.py: the referral notice and its log (ADR 0022)."""

from unittest import mock

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from core.tests.support import make_center, make_interaction, make_question, make_referral, make_user
from qa.models import Referral
from qa.services import open_referral
from telegram_bot.models import TelegramMessage
from telegram_bot.services import QUESTION_MAX, notify_referral, referral_notice, resend
from telegram_bot.tests.support import FakeClient

GROUP = -1001234567890


class NoticeTests(TestCase):
    """What the group reads: in the center's language, escaped, without the asker."""

    def referral(self, text='Can I pray <sitting>?', lang='en', languages=('fr',), **fields):
        center = make_center(telegram_chat_id=GROUP, languages=list(languages))
        question = make_question(center=center, text=text, lang=lang, **fields)
        return make_referral(question=make_interaction(question=question, decision='refer').question)

    def test_in_the_center_language_with_reason_language_and_follow_up_number(self):
        referral = self.referral()
        notice = referral_notice(referral)
        self.assertIn('Motif', notice)
        self.assertIn('Non couverte par les sources', notice)
        self.assertIn('Anglais', notice)
        self.assertIn(f'<code>{referral.question.uuid}</code>', notice)

    def test_question_is_escaped_and_the_asker_never_shown(self):
        asker = make_user(email='asker@example.com')
        notice = referral_notice(self.referral(asker=asker))
        self.assertIn('<blockquote>Can I pray &lt;sitting&gt;?</blockquote>', notice)
        self.assertNotIn('asker@example.com', notice)

    def test_center_without_languages_uses_the_default_language(self):
        self.assertIn('New question referred to your center', referral_notice(self.referral(languages=())))

    def test_long_question_is_cut(self):
        notice = referral_notice(self.referral(text='x' * (QUESTION_MAX + 50)))
        self.assertIn('x' * QUESTION_MAX + '…', notice)
        self.assertNotIn('x' * (QUESTION_MAX + 1), notice)

    def test_admin_link_only_with_site_url(self):
        referral = self.referral()
        self.assertNotIn('href', referral_notice(referral))
        with override_settings(SITE_URL='https://api.musnid.online'):
            self.assertIn(f'href="https://api.musnid.online/admin/qa/question/?q={referral.question.uuid}"',
                          referral_notice(referral))


class NotifyTests(TestCase):
    """``notify_referral`` and ``resend`` log every attempt; nothing is sent without a token or a group."""

    def setUp(self):
        self.referral = make_referral(center=make_center(telegram_chat_id=GROUP))

    def test_sent_notice_is_logged_with_its_message_id(self):
        client = FakeClient()
        message = notify_referral(self.referral, client)
        self.assertEqual(client.sent, [(GROUP, message.text)])
        self.assertEqual((message.status, message.message_id, message.chat_id),
                         (TelegramMessage.Status.SENT, 101, GROUP))
        self.assertEqual(message.kind, TelegramMessage.Kind.REFERRAL_NOTICE)

    def test_failed_notice_is_logged_not_raised(self):
        with self.assertLogs('telegram_bot.services', 'WARNING'):
            message = notify_referral(self.referral, FakeClient(error='sendMessage: 403 Forbidden: bot was kicked'))
        message.refresh_from_db()
        self.assertEqual((message.status, message.message_id), (TelegramMessage.Status.FAILED, None))
        self.assertEqual(message.error, 'sendMessage: 403 Forbidden: bot was kicked')

    def test_nothing_sent_without_token_or_group(self):
        client = FakeClient(enabled=False)
        self.assertIsNone(notify_referral(self.referral, client))
        self.assertIsNone(notify_referral(make_referral(), FakeClient()))  # center without a group
        self.assertFalse(TelegramMessage.objects.exists())

    def test_resend_adds_an_attempt_and_keeps_the_failed_one(self):
        with self.assertLogs('telegram_bot.services', 'WARNING'):
            failed = notify_referral(self.referral, FakeClient(error='sendMessage: Timeout'))
        attempt = resend(failed, FakeClient())
        self.assertEqual(attempt.status, TelegramMessage.Status.SENT)
        self.assertEqual(TelegramMessage.objects.count(), 2)

    def test_resend_refusals(self):
        sent = notify_referral(self.referral, FakeClient())
        with self.assertRaises(ValidationError) as caught:
            resend(sent, FakeClient())
        self.assertEqual(caught.exception.code, 'telegram_not_failed')
        sent.status, sent.message_id = TelegramMessage.Status.FAILED, None
        with self.assertRaises(ValidationError) as caught:
            resend(sent, FakeClient(enabled=False))
        self.assertEqual(caught.exception.code, 'telegram_unavailable')


class ReceiverTests(TestCase):
    """Opening a referral notifies the center once the transaction commits."""

    def test_open_referral_notifies_after_commit(self):
        question = make_interaction(question=make_question(center=make_center(telegram_chat_id=GROUP)),
                                    decision='refer').question
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
