"""
What the bot sends (ADR 0022).

``notify_referral`` sends a referred question, with an "Answer" button, to
every linked specialist of its center in their private chat with the bot (and
to the center's group when one is connected), and logs each attempt as a
``TelegramMessage``. A Telegram failure is logged and
saved, never raised: the asker's question is already saved and answered.
``resend`` tries a failed notice again, as a new logged attempt.
"""

import logging
from html import escape

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import translation
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, ngettext

from core.models import Language
from telegram_bot.client import TelegramClient, TelegramError
from telegram_bot.models import TelegramMessage

logger = logging.getLogger(__name__)

#: Prefix of the "Answer" button's callback data, followed by the question's uuid
ANSWER_CALLBACK = 'answer:'

#: Longest question text put in a notice; Telegram refuses messages over 4,096 characters
QUESTION_MAX = 3000


def notice_language(center):
    """The language of the center's notices: the first language it serves, else ``settings.LANGUAGE_CODE``."""
    return center.languages[0] if center.languages else settings.LANGUAGE_CODE


def referral_notice(referral, language):
    """
    The notice of ``referral`` in Telegram HTML, in ``language``.

    Carries the reason, the question's language, the follow-up number and the
    question. Never the asker: specialists do not need to know who asked.
    """
    question = referral.question
    text = question.text if len(question.text) <= QUESTION_MAX else question.text[:QUESTION_MAX] + '…'
    with translation.override(language):
        question_language = Language(question.lang).label if question.lang in Language.values else '-'
        lines = [
            f'<b>{escape(_("New question referred to your center"))}</b>',
            f'{escape(_("Reason"))}: {escape(str(referral.get_reason_display()))}',
            f'{escape(_("Language"))}: {escape(str(question_language))}',
            f'{escape(_("Follow-up number"))}: <code>{question.uuid}</code>',
            '',
            f'<blockquote>{escape(text)}</blockquote>',
        ]
        if referral.mode == referral.Mode.LIVE:
            minutes = max(1, round(settings.REFERRAL_LIVE_SECONDS / 60))
            lines += ['', escape(ngettext(
                '⏱ Answer within %(minutes)d minute to reply live; after that, it stays in the center\'s queue.',
                '⏱ Answer within %(minutes)d minutes to reply live; after that, it stays in the center\'s queue.',
                minutes) % {'minutes': minutes})]
        else:
            lines += ['', escape(_('🎫 Ticket: answer when you can; the asker will see your answer in their '
                                   'history.'))]
    return '\n'.join(lines)


def answer_keyboard(question, language):
    """The "Answer" button under a notice; its callback carries the question's public ``uuid`` (43 bytes)."""
    with translation.override(language):
        label = _('✍️ Answer')
    return {'inline_keyboard': [[{'text': label, 'callback_data': f'{ANSWER_CALLBACK}{question.uuid}'}]]}


def recipients(referral):
    """
    Where the notice of ``referral`` goes, as ``[(chat_id, language)]``.

    Every active, linked member of the center, privately, in their own language;
    and the center's group, if one is connected, in the center's language.
    """
    members = get_user_model().objects.filter(
        is_active=True, telegram_chat_id__isnull=False,
        memberships__center=referral.center, memberships__is_active=True,
    ).distinct()
    chats = [(user.telegram_chat_id, user.preferred_lang) for user in members]
    if referral.center.telegram_chat_id is not None:
        chats.append((referral.center.telegram_chat_id, notice_language(referral.center)))
    return chats


def send_notice(referral, chat_id, language, client):
    """Send the notice of ``referral`` with its "Answer" button to ``chat_id``; log and return the attempt."""
    message = TelegramMessage(referral=referral, kind=TelegramMessage.Kind.REFERRAL_NOTICE, chat_id=chat_id,
                              text=referral_notice(referral, language))
    try:
        sent = client.send_message(chat_id, message.text, reply_markup=answer_keyboard(referral.question, language))
    except TelegramError as error:
        message.status, message.error = TelegramMessage.Status.FAILED, str(error)
        logger.warning('Telegram notice of referral %s failed: %s', referral.question.uuid, error)
    else:
        message.status, message.message_id = TelegramMessage.Status.SENT, sent['message_id']
    message.save()
    return message


def notify_referral(referral, client=None):
    """
    Send ``referral`` to every recipient (linked specialists, and the group if any); return the attempts.

    Returns an empty list without calling Telegram when the bot is off (no token)
    or nobody of the center is reachable.
    """
    client = client or TelegramClient()
    if not client.enabled:
        return []
    return [send_notice(referral, chat_id, language, client) for chat_id, language in recipients(referral)]


def resend(message, client=None):
    """
    Send a failed notice again to the same chat; return the new ``TelegramMessage`` (sent or failed).

    The failed row stays as the record of the first attempt.

    Raises:
        ValidationError: ``telegram_not_failed`` when ``message`` was sent, or
            ``telegram_unavailable`` when the bot is off.
    """
    if message.status != TelegramMessage.Status.FAILED:
        raise ValidationError(gettext_lazy('Only failed messages can be sent again.'), code='telegram_not_failed')
    client = client or TelegramClient()
    if not client.enabled:
        raise ValidationError(gettext_lazy('The bot has no token.'), code='telegram_unavailable')
    member = get_user_model().objects.filter(telegram_chat_id=message.chat_id).first()
    language = member.preferred_lang if member else notice_language(message.referral.center)
    return send_notice(message.referral, message.chat_id, language, client)
