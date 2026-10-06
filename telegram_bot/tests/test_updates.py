"""Tests for telegram_bot/updates.py: linking with /start and answering by replying in the group (ADR 0023)."""

from django.test import TestCase
from django.utils import timezone

from core.models import Center, Membership
from core.tests.support import make_center, make_membership, make_referral, make_user
from qa.models import AnswerRevision, Referral
from telegram_bot.linking import create_group_link, create_link
from telegram_bot.models import TelegramMessage
from telegram_bot.services import notify_referral
from telegram_bot.tests.support import FakeClient
from telegram_bot.updates import handle_update

GROUP = -1001234567890
SPECIALIST_ID = 111


def private(text, sender=SPECIALIST_ID):
    return {'update_id': 1, 'message': {'message_id': 9, 'from': {'id': sender}, 'text': text,
                                        'chat': {'id': sender, 'type': 'private'}}}


def group_reply(to_message_id, text='The answer from the specialist.', sender=SPECIALIST_ID, chat=GROUP):
    message = {'message_id': 77, 'from': {'id': sender}, 'chat': {'id': chat, 'type': 'group'},
               'reply_to_message': {'message_id': to_message_id}}
    if text is not None:
        message['text'] = text
    return {'update_id': 2, 'message': message}


class StartTests(TestCase):
    """``/start <code>`` links the sender; without a code the bot welcomes them."""

    def test_start_with_a_code_links_and_confirms(self):
        user = make_user(full_name='Amina', preferred_lang='fr')
        code = create_link(user, FakeClient())[0].rsplit('=', 1)[1]
        client = FakeClient()
        self.assertEqual(handle_update(private(f'/start {code}'), client), 'linked')
        user.refresh_from_db()
        self.assertEqual(user.telegram_chat_id, SPECIALIST_ID)
        self.assertIn('Amina', client.replies[0][2])
        self.assertIn('Votre compte Telegram', client.replies[0][2])

    def test_start_without_a_code_welcomes_in_the_telegram_language(self):
        client = FakeClient()
        update = private('/start')
        update['message']['from']['language_code'] = 'fr'
        self.assertEqual(handle_update(update, client), 'welcomed')
        self.assertIn('Bienvenue sur Musnid', client.replies[0][2])
        make_user(telegram_chat_id=SPECIALIST_ID, full_name='Amina', preferred_lang='en')
        handle_update(private('/start'), client)
        self.assertIn('Welcome back, Amina', client.replies[1][2])

    def test_start_with_a_bad_code(self):
        client = FakeClient()
        self.assertEqual(handle_update(private('/start nope'), client), 'refused')
        self.assertIn('invalid or expired', client.replies[0][2])


class AnswerTests(TestCase):
    """A linked member's reply to the notice becomes the answer the asker sees."""

    def setUp(self):
        self.center = make_center(telegram_chat_id=GROUP, languages=['en'])
        self.referral = make_referral(center=self.center)
        [self.notice] = notify_referral(self.referral, FakeClient())  # the group only: nobody is linked yet
        self.specialist = make_membership(center=self.center, user=make_user(telegram_chat_id=SPECIALIST_ID)).user
        self.client_ = FakeClient()

    def test_reply_is_saved_as_the_answer_and_the_referral_answered(self):
        outcome = handle_update(group_reply(self.notice.message_id), self.client_)
        self.assertEqual(outcome, 'answered')
        revision = AnswerRevision.objects.get()
        self.assertEqual((revision.question, revision.author, revision.text, revision.reason, revision.note),
                         (self.referral.question, self.specialist, 'The answer from the specialist.',
                          AnswerRevision.Reason.SPECIALIST_ANSWER, 'Telegram'))
        self.referral.refresh_from_db()
        self.assertEqual(self.referral.status, Referral.Status.ANSWERED)
        self.assertEqual(self.client_.replies, [(GROUP, 77, '✅ The answer was sent to the asker.')])

    def test_unlinked_sender_is_told_to_link(self):
        self.assertEqual(handle_update(group_reply(self.notice.message_id, sender=222), self.client_), 'refused')
        self.assertIn('Connect Telegram from your Musnid dashboard first', self.client_.replies[0][2])
        self.assertFalse(AnswerRevision.objects.exists())

    def test_linked_user_outside_the_center_is_refused(self):
        make_user(telegram_chat_id=333)
        self.assertEqual(handle_update(group_reply(self.notice.message_id, sender=333), self.client_), 'refused')
        self.assertEqual(self.client_.replies[0][2], 'You cannot revise answers of this center.')

    def test_reply_without_text_is_refused(self):
        self.assertEqual(handle_update(group_reply(self.notice.message_id, text=None), self.client_), 'refused')
        self.assertEqual(self.client_.replies[0][2], 'Send the answer as text.')

    def test_other_messages_are_ignored(self):
        self.assertIsNone(handle_update(group_reply(999), self.client_))  # a reply to another message
        self.assertIsNone(handle_update(group_reply(self.notice.message_id, chat=-555), self.client_))
        self.assertIsNone(handle_update({'update_id': 3, 'my_chat_member': {}}, self.client_))
        self.assertEqual(self.client_.replies, [])

    def test_replies_in_a_disconnected_group_are_ignored(self):
        Center.objects.filter(pk=self.center.pk).update(telegram_chat_id=None, updated_at=timezone.now())
        self.assertIsNone(handle_update(group_reply(self.notice.message_id), self.client_))
        self.assertFalse(AnswerRevision.objects.exists())

    def test_a_failed_notice_cannot_be_answered(self):
        TelegramMessage.objects.update(status=TelegramMessage.Status.FAILED, updated_at=timezone.now())
        self.assertIsNone(handle_update(group_reply(self.notice.message_id), self.client_))


class GroupConnectionUpdateTests(TestCase):
    """The bot added through the startgroup link connects the group; removal and upgrade follow it."""

    def setUp(self):
        self.center = make_center(languages=['en'])
        self.admin = make_membership(center=self.center, role=Membership.Role.CENTER_ADMIN).user
        self.client_ = FakeClient()

    def start_in_group(self, text, chat=GROUP):
        return {'update_id': 4, 'message': {'message_id': 1, 'from': {'id': SPECIALIST_ID}, 'text': text,
                                            'chat': {'id': chat, 'type': 'group', 'title': 'Center group'}}}

    def test_start_with_the_code_connects_and_confirms(self):
        code = create_group_link(self.center, self.admin, FakeClient())[0].rsplit('=', 1)[1]
        self.assertEqual(handle_update(self.start_in_group(f'/start@musnid_test_bot {code}'), self.client_),
                         'connected')
        self.center.refresh_from_db()
        self.assertEqual(self.center.telegram_chat_id, GROUP)
        self.assertIn('This group is now connected to', self.client_.replies[0][2])

    def test_bad_code_is_refused_and_plain_start_ignored(self):
        self.assertEqual(handle_update(self.start_in_group('/start nope'), self.client_), 'refused')
        self.assertIsNone(handle_update(self.start_in_group('/start'), self.client_))

    def test_removing_the_bot_disconnects_and_upgrade_moves(self):
        Center.objects.filter(pk=self.center.pk).update(telegram_chat_id=GROUP, updated_at=timezone.now())
        upgrade = {'update_id': 5, 'message': {'message_id': 2, 'chat': {'id': GROUP, 'type': 'group'},
                                               'migrate_to_chat_id': GROUP - 1}}
        self.assertEqual(handle_update(upgrade, self.client_), 'moved')
        removed = {'update_id': 6, 'my_chat_member': {'chat': {'id': GROUP - 1, 'type': 'supergroup'},
                                                      'new_chat_member': {'status': 'kicked'}}}
        self.assertEqual(handle_update(removed, self.client_), 'disconnected')
        self.center.refresh_from_db()
        self.assertIsNone(self.center.telegram_chat_id)


class PrivateAnswerTests(TestCase):
    """The private flow: the Answer button opens a reply box; the reply is the answer."""

    def setUp(self):
        self.center = make_center(languages=['ar'])
        self.specialist = make_membership(center=self.center, user=make_user(
            telegram_chat_id=SPECIALIST_ID, preferred_lang='en')).user
        self.referral = make_referral(center=self.center)
        [self.notice] = notify_referral(self.referral, FakeClient())
        self.client_ = FakeClient()

    def press(self, data=None, sender=SPECIALIST_ID):
        data = data or f'answer:{self.referral.question.uuid}'
        return handle_update({'update_id': 7, 'callback_query': {
            'id': 'cb1', 'from': {'id': sender}, 'data': data,
            'message': {'message_id': self.notice.message_id, 'chat': {'id': SPECIALIST_ID, 'type': 'private'}}}},
            self.client_)

    def private_reply(self, to_message_id, text='The answer, privately.'):
        return handle_update({'update_id': 8, 'message': {
            'message_id': 90, 'from': {'id': SPECIALIST_ID}, 'text': text,
            'chat': {'id': SPECIALIST_ID, 'type': 'private'}, 'reply_to_message': {'message_id': to_message_id}}},
            self.client_)

    def test_button_opens_the_reply_box_and_the_reply_is_the_answer(self):
        self.assertEqual(self.press(), 'prompted')
        self.assertTrue(self.client_.markups[0]['force_reply'])
        self.assertEqual(self.client_.callbacks, [('cb1', '')])
        prompt = TelegramMessage.objects.get(kind=TelegramMessage.Kind.ANSWER_PROMPT)
        self.assertEqual(self.private_reply(prompt.message_id), 'answered')
        self.referral.refresh_from_db()
        self.assertEqual(self.referral.status, Referral.Status.ANSWERED)
        self.assertEqual(AnswerRevision.objects.get().text, 'The answer, privately.')

    def test_replying_to_the_notice_itself_also_answers(self):
        self.assertEqual(self.private_reply(self.notice.message_id), 'answered')

    def test_button_refusals(self):
        make_user(telegram_chat_id=999)
        self.assertEqual(self.press(sender=999), 'refused')  # linked, but not a member of the center
        self.assertEqual(self.press(sender=555), 'refused')  # not linked
        self.assertIsNone(self.press(data='answer:not-a-uuid'))
        self.assertFalse(TelegramMessage.objects.filter(kind=TelegramMessage.Kind.ANSWER_PROMPT).exists())

    def test_other_private_messages_get_help(self):
        self.assertEqual(handle_update(private('hello'), self.client_), 'help')
        self.assertIn('Tap ✍️ Answer', self.client_.replies[0][2])

    def test_the_first_answer_wins(self):
        self.assertEqual(self.private_reply(self.notice.message_id), 'answered')
        self.assertEqual(self.private_reply(self.notice.message_id, text='A second answer.'), 'refused')
        self.assertIn('already answered by', self.client_.replies[-1][2])
        self.assertEqual(self.press(), 'refused')
        self.assertIn('already answered by', self.client_.callbacks[-1][1])
        self.assertEqual(AnswerRevision.objects.count(), 1)

