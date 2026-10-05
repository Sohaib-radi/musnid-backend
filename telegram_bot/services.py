"""
What the bot sends (ADR 0022).

``notify_referral`` posts a referred question to its center's Telegram group
and logs the attempt as a ``TelegramMessage``. A Telegram failure is logged and
saved, never raised: the asker's question is already saved and answered.
``resend`` tries a failed notice again, as a new logged attempt.
"""

import logging
from html import escape

from django.conf import settings
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from core.models import Language
from telegram_bot.client import TelegramClient, TelegramError
from telegram_bot.models import TelegramMessage

logger = logging.getLogger(__name__)

#: Longest question text put in a notice; Telegram refuses messages over 4,096 characters
QUESTION_MAX = 3000


def notice_language(center):
    """The language of the center's notices: the first language it serves, else ``settings.LANGUAGE_CODE``."""
    return center.languages[0] if center.languages else settings.LANGUAGE_CODE


def referral_notice(referral):
    """
    The notice of ``referral`` in Telegram HTML, in the center's language.

    Carries the reason, the question's language, the follow-up number and the
    question; a link to the question in the admin when ``settings.SITE_URL`` is
    set. Never the asker: the group does not need to know who asked.
    """
    question = referral.question
    text = question.text if len(question.text) <= QUESTION_MAX else question.text[:QUESTION_MAX] + '…'
    with translation.override(notice_language(referral.center)):
        language = Language(question.lang).label if question.lang in Language.values else '-'
        lines = [
            f'<b>{escape(_("New question referred to your center"))}</b>',
            f'{escape(_("Reason"))}: {escape(str(referral.get_reason_display()))}',
            f'{escape(_("Language"))}: {escape(str(language))}',
            f'{escape(_("Follow-up number"))}: <code>{question.uuid}</code>',
            '',
            f'<blockquote>{escape(text)}</blockquote>',
        ]
        if settings.SITE_URL:
            url = f'{settings.SITE_URL}{reverse("admin:qa_question_changelist")}?q={question.uuid}'
            lines += ['', f'<a href="{escape(url)}">{escape(_("Open in the admin"))}</a>']
    return '\n'.join(lines)


def notify_referral(referral, client=None):
    """
    Post ``referral`` to its center's Telegram group; return the logged ``TelegramMessage``.

    Returns ``None`` without calling Telegram when the bot is off (no token) or
    the center has no group (``Center.telegram_chat_id``).
    """
    client = client or TelegramClient()
    chat_id = referral.center.telegram_chat_id
    if not client.enabled or chat_id is None:
        return None
    message = TelegramMessage(referral=referral, kind=TelegramMessage.Kind.REFERRAL_NOTICE, chat_id=chat_id,
                              text=referral_notice(referral))
    try:
        sent = client.send_message(chat_id, message.text)
    except TelegramError as error:
        message.status, message.error = TelegramMessage.Status.FAILED, str(error)
        logger.warning('Telegram notice of referral %s failed: %s', referral.question.uuid, error)
    else:
        message.status, message.message_id = TelegramMessage.Status.SENT, sent['message_id']
    message.save()
    return message


def resend(message, client=None):
    """
    Send a failed notice again; return the new ``TelegramMessage`` (sent or failed).

    The failed row stays as the record of the first attempt.

    Raises:
        ValidationError: ``telegram_not_failed`` when ``message`` was sent, or
            ``telegram_unavailable`` when the bot is off or the center has no group.
    """
    if message.status != TelegramMessage.Status.FAILED:
        raise ValidationError(gettext_lazy('Only failed messages can be sent again.'), code='telegram_not_failed')
    attempt = notify_referral(message.referral, client)
    if attempt is None:
        raise ValidationError(gettext_lazy('The bot has no token, or the center has no Telegram group.'),
                              code='telegram_unavailable')
    return attempt
