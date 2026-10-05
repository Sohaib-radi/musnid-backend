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
- A reply, in a center's group, to the bot's notice of a referral is a
  specialist's answer: it is saved through ``qa.services.revise``, so the asker
  sees it at once and the referral becomes answered. Only linked, allowed users
  can answer; others get a short explanation.

Everything else is ignored. The bot's own replies are plain text in the
language of the person or center they address.
"""

import logging

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import translation
from django.utils.translation import gettext as _

from qa.models import AnswerRevision
from qa.services import revise
from telegram_bot.client import TelegramClient, TelegramError
from telegram_bot.linking import connect_group, disconnect_group, link_account, move_group
from telegram_bot.models import TelegramMessage
from telegram_bot.services import notice_language

logger = logging.getLogger(__name__)

#: Internal note of a revision written in Telegram (a brand name: never translated)
TELEGRAM_NOTE = 'Telegram'


GROUP_TYPES = ('group', 'supergroup')


def handle_update(update, client=None):
    """
    Act on one Telegram ``update``; return what was done or ``None``.

    Outcomes: ``linked``, ``connected``, ``disconnected``, ``moved``, ``answered``, ``refused``.
    """
    client = client or TelegramClient()
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
    if chat.get('type') in GROUP_TYPES and message.get('reply_to_message'):
        return _answer(client, message, text)
    return None


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
        _reply(client, message, _('To answer questions, open the Telegram link your center gives you.'))
        return 'refused'
    try:
        user = link_account(parts[1], message['from']['id'])
    except ValidationError as error:
        _reply(client, message, ' '.join(error.messages))
        return 'refused'
    with translation.override(user.preferred_lang):
        _reply(client, message, _('Your Telegram account is now linked to %(name)s. Reply to the bot\'s messages '
                                  'in your center\'s group to answer questions.') % {'name': user.full_name})
    return 'linked'


def _answer(client, message, text):
    """Save a reply to a referral notice as the answer, if the sender is a linked, allowed user."""
    notice = TelegramMessage.objects.select_related('referral__question__center').filter(
        chat_id=message['chat']['id'], message_id=message['reply_to_message']['message_id'],
        kind=TelegramMessage.Kind.REFERRAL_NOTICE, status=TelegramMessage.Status.SENT,
    ).first()
    if notice is None or notice.referral.question.center.telegram_chat_id != message['chat']['id']:
        return None  # a reply to something else, or in a group the center has since disconnected
    question = notice.referral.question
    with translation.override(notice_language(question.center)):
        author = get_user_model().objects.filter(telegram_chat_id=message['from']['id'], is_active=True).first()
        if author is None:
            _reply(client, message, _('Link your Telegram account first: ask your center for your link.'))
            return 'refused'
        if not text:
            _reply(client, message, _('Send the answer as text.'))
            return 'refused'
        try:
            revise(question, author, text, AnswerRevision.Reason.SPECIALIST_ANSWER, note=TELEGRAM_NOTE)
        except ValidationError as error:
            _reply(client, message, ' '.join(error.messages))
            return 'refused'
        _reply(client, message, _('The answer was sent to the asker.'))
    return 'answered'


def _reply(client, message, text):
    """Reply to ``message``; a failure is logged, since the update itself was handled."""
    try:
        client.reply(message['chat']['id'], message['message_id'], text)
    except TelegramError as error:
        logger.warning('Telegram reply failed: %s', error)
