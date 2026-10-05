"""
What the bot does with the updates Telegram sends (ADR 0023).

``handle_update`` is fed by polling locally (``telegram_poll``) and by the
webhook in production; both behave the same.

- ``/start <code>`` in a private chat links the person's Telegram account
  (``telegram_bot.linking``).
- ``/start <code>`` in a group (sent by Telegram when a center admin adds the
  bot through the ``startgroup`` link) connects that group to the center.
  Removing the bot disconnects it; a group upgraded to a supergroup keeps its
  center under its new ID.
- Notices of referrals reach each linked specialist in their private chat with
  the bot, with an "Answer" button. Tapping it opens Telegram's reply box (a
  ``force_reply`` prompt); the reply, or a direct reply to the notice, is the
  specialist's answer: it is saved through ``qa.services.revise``, so the asker
  sees it at once and the referral becomes answered. Replies in a connected
  group work the same way. Only linked, allowed users can answer; others get a
  short explanation.

Everything else is ignored. The bot's own replies are plain text in the
language of the person or center they address.
"""

import logging
import uuid
from html import escape

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import translation
from django.utils.translation import gettext as _

from qa.models import AnswerRevision, Referral
from qa.services import can_revise, revise
from agents.replies import REPLY_LANGUAGES
from telegram_bot.client import TelegramClient, TelegramError
from telegram_bot.linking import connect_group, disconnect_group, link_account, move_group
from telegram_bot.models import TelegramMessage
from telegram_bot.services import ANSWER_CALLBACK, notice_language

logger = logging.getLogger(__name__)

#: Internal note of a revision written in Telegram (a brand name: never translated)
TELEGRAM_NOTE = 'Telegram'


GROUP_TYPES = ('group', 'supergroup')


def handle_update(update, client=None):
    """
    Act on one Telegram ``update``; return what was done or ``None``.

    Outcomes: ``welcomed``, ``linked``, ``connected``, ``disconnected``, ``moved``, ``prompted``,
    ``answered``, ``help``, ``refused``.
    """
    client = client or TelegramClient()
    callback = update.get('callback_query')
    if callback:
        return _prompt(client, callback)
    member = update.get('my_chat_member')
    if member:
        return _membership_changed(member)
    message = update.get('message') or {}
    chat = message.get('chat') or {}
    text = (message.get('text') or '').strip()
    if chat.get('type') in GROUP_TYPES and message.get('migrate_to_chat_id'):
        move_group(chat['id'], message['migrate_to_chat_id'])
        return 'moved'
    if chat.get('type') == 'private' and text.startswith('/start'):
        return _start(client, message, text)
    if chat.get('type') in GROUP_TYPES and text.startswith('/start'):
        return _connect(client, message, text)
    if chat.get('type') in (*GROUP_TYPES, 'private') and message.get('reply_to_message'):
        return _answer(client, message, text)
    if chat.get('type') == 'private':
        return _help(client, message)
    return None


def telegram_language(message):
    """The sender's Telegram app language when the bot speaks it, else ``settings.LANGUAGE_CODE``."""
    code = ((message.get('from') or {}).get('language_code') or '')[:2]
    return code if code in REPLY_LANGUAGES else settings.LANGUAGE_CODE


def _welcome(client, message):
    """``/start`` without a code: welcome a linked specialist back, or present Musnid to a newcomer."""
    user = _linked_user(message['from']['id'])
    with translation.override(user.preferred_lang if user else telegram_language(message)):
        if user:
            text = _('👋 Welcome back, %(name)s. Questions for your center arrive here: tap ✍️ Answer to reply; '
                     'the asker sees your answer at once.') % {'name': user.full_name}
        else:
            text = _('👋 Welcome to Musnid.\n\nMusnid answers questions about Islam from verified sources. When a '
                     'question needs a specialist, it is sent here to the specialists of a center, who answer it '
                     'directly.\n\nAre you a specialist? Connect Telegram from your Musnid dashboard to receive '
                     'questions.')
        _reply(client, message, text)
    return 'welcomed'


def _linked_user(telegram_id):
    """The active user whose Telegram account is ``telegram_id``, or ``None``."""
    return get_user_model().objects.filter(telegram_chat_id=telegram_id, is_active=True).first()


def _help(client, message):
    """Explain, in a private chat, how to answer (linked users) or how to link (others)."""
    user = _linked_user(message['from']['id'])
    with translation.override(user.preferred_lang if user else telegram_language(message)):
        if user:
            _reply(client, message, _('Tap ✍️ Answer under a question to reply to it.'))
        else:
            _reply(client, message, _('To answer questions, connect Telegram from your Musnid dashboard.'))
    return 'help'


def _prompt(client, callback):
    """The "Answer" button: open Telegram's reply box for that question, if the user may answer it."""
    data = callback.get('data') or ''
    message = callback.get('message') or {}
    user = _linked_user(callback['from']['id'])
    referral = None
    if data.startswith(ANSWER_CALLBACK):
        referral = Referral.objects.select_related('question__center').filter(
            question__uuid=_uuid_or_none(data[len(ANSWER_CALLBACK):])).first()
    with translation.override(user.preferred_lang if user else settings.LANGUAGE_CODE):
        if referral is None or not message:
            _answer_callback(client, callback, '')
            return None  # not an Answer button, or a forged one
        question = referral.question
        if user is None:
            _answer_callback(client, callback, _('Connect Telegram from your Musnid dashboard first.'))
            return 'refused'
        if not can_revise(user, question):
            _answer_callback(client, callback, _('You cannot revise answers of this center.'))
            return 'refused'
        excerpt = question.text if len(question.text) <= 300 else question.text[:300] + '…'
        text = f'<b>{escape(_("✍️ Write your answer to:"))}</b>\n<blockquote>{escape(excerpt)}</blockquote>'
        markup = {'force_reply': True, 'input_field_placeholder': str(_('Your answer'))}
        chat_id = message['chat']['id']
        try:
            sent = client.send_message(chat_id, text, reply_markup=markup)
        except TelegramError as error:
            logger.warning('Telegram answer prompt failed: %s', error)
            _answer_callback(client, callback, '')
            return 'refused'
        # Logged so the reply to the prompt is matched to its referral
        TelegramMessage.objects.create(
            referral=referral, kind=TelegramMessage.Kind.ANSWER_PROMPT, chat_id=chat_id,
            message_id=sent['message_id'], status=TelegramMessage.Status.SENT, text=text,
        )
        _answer_callback(client, callback, '')
    return 'prompted'


def _uuid_or_none(value):
    """``value`` as a UUID, or ``None`` when it is not one (a forged callback)."""
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def _answer_callback(client, callback, text):
    """Acknowledge a button press; a failure is logged, since the update itself was handled."""
    try:
        client.answer_callback(callback['id'], text)
    except TelegramError as error:
        logger.warning('Telegram callback answer failed: %s', error)


def _membership_changed(member):
    """Disconnect a center's group when the bot is removed from it."""
    status = (member.get('new_chat_member') or {}).get('status')
    chat = member.get('chat') or {}
    if chat.get('type') in GROUP_TYPES and status in ('left', 'kicked') and disconnect_group(chat['id']):
        return 'disconnected'
    return None


def _connect(client, message, text):
    """Connect the group with the code Telegram sent as ``/start <code>`` (or ``/start@bot <code>``)."""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return None  # someone typed /start in the group: nothing to connect
    try:
        center = connect_group(parts[1], message['chat']['id'], message['from']['id'])
    except ValidationError as error:
        _reply(client, message, ' '.join(error.messages))
        return 'refused'
    with translation.override(notice_language(center)):
        _reply(client, message, _('This group is now connected to %(center)s. Referred questions will arrive '
                                  'here; linked specialists answer by replying to them.') % {'center': center.name})
    return 'connected'


def _start(client, message, text):
    """Link the sender with the code after ``/start``, or explain how to get one."""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return _welcome(client, message)
    try:
        user = link_account(parts[1], message['from']['id'])
    except ValidationError as error:
        _reply(client, message, ' '.join(error.messages))
        return 'refused'
    with translation.override(user.preferred_lang):
        _reply(client, message, _('✅ Your Telegram account is now linked to %(name)s. Questions for your center '
                                  'will arrive here: tap ✍️ Answer to reply.') % {'name': user.full_name})
    return 'linked'


def _answer(client, message, text):
    """Save a reply to a notice or an answer prompt as the answer, if the sender is a linked, allowed user."""
    chat = message['chat']
    notice = TelegramMessage.objects.select_related('referral__question__center').filter(
        chat_id=chat['id'], message_id=message['reply_to_message']['message_id'],
        kind__in=[TelegramMessage.Kind.REFERRAL_NOTICE, TelegramMessage.Kind.ANSWER_PROMPT],
        status=TelegramMessage.Status.SENT,
    ).first()
    is_group = chat['type'] in GROUP_TYPES
    if notice is None:
        return _help(client, message) if not is_group else None  # a reply to something else
    question = notice.referral.question
    if is_group and question.center.telegram_chat_id != chat['id']:
        return None  # a group the center has since disconnected
    author = _linked_user(message['from']['id'])
    language = notice_language(question.center) if is_group or author is None else author.preferred_lang
    with translation.override(language):
        if author is None:
            _reply(client, message, _('Connect Telegram from your Musnid dashboard first.'))
            return 'refused'
        if not text:
            _reply(client, message, _('Send the answer as text.'))
            return 'refused'
        try:
            revise(question, author, text, AnswerRevision.Reason.SPECIALIST_ANSWER, note=TELEGRAM_NOTE)
        except ValidationError as error:
            _reply(client, message, ' '.join(error.messages))
            return 'refused'
        _reply(client, message, _('✅ The answer was sent to the asker.'))
    return 'answered'


def _reply(client, message, text):
    """Reply to ``message``; a failure is logged, since the update itself was handled."""
    try:
        client.reply(message['chat']['id'], message['message_id'], text)
    except TelegramError as error:
        logger.warning('Telegram reply failed: %s', error)
