"""
Linking Telegram accounts to users and Telegram groups to centers (ADR 0023).

- ``create_link`` makes a one-time ``t.me/<bot>?start=<code>`` link, valid
  ``LINK_MINUTES``. When the person opens it and presses Start, the bot receives
  ``/start <code>`` and ``link_account`` saves their Telegram ID on the user
  (``User.telegram_chat_id``). From then on, their replies in a center's group
  are answers by that user.
- ``create_group_link`` makes a one-time ``t.me/<bot>?startgroup=<code>`` link
  for a center admin. Telegram asks which group to add the bot to; the bot then
  receives ``/start <code>`` in that group and ``connect_group`` saves the group
  on the center. One group per center, and a group serves one center only.
- ``disconnect_center`` lets a center admin disconnect the group from the
  dashboard; the bot says goodbye and leaves it.
"""

import hashlib
import logging
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils import translation
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django.views.decorators.debug import sensitive_variables

from core.models import Center, Membership
from telegram_bot.client import TelegramClient, TelegramError
from telegram_bot.models import TelegramLinkCode
from telegram_bot.services import notice_language

logger = logging.getLogger(__name__)

#: How long a link can be used; long enough to scan it, short enough not to leak
LINK_MINUTES = 10


@sensitive_variables('code')
def code_hash(code):
    """SHA-256 hex digest of a link code; only the digest is stored."""
    return hashlib.sha256(code.encode()).hexdigest()


@sensitive_variables('code')
def create_link(user, client=None):
    """
    A one-time link for ``user`` to link their Telegram account; return ``(url, expires_at)``.

    Calls ``getMe`` for the bot's username, so the link follows the configured bot.

    Raises:
        ValidationError: ``telegram_link_inactive_user`` for a deactivated user.
        TelegramError: when Telegram cannot be reached.
    """
    if not user.is_active:
        raise ValidationError(_('A deactivated account cannot link Telegram.'), code='telegram_link_inactive_user')
    username = (client or TelegramClient()).username()
    code, expires_at = _new_code(user)
    return f'https://t.me/{username}?start={code}', expires_at


@sensitive_variables('code')
def create_group_link(center, user, client=None):
    """
    A one-time link that adds the bot to a group and connects it to ``center``; return ``(url, expires_at)``.

    Raises:
        ValidationError: ``telegram_not_center_admin`` unless ``user`` is an
            active center admin of the operational ``center``.
        TelegramError: when Telegram cannot be reached.
    """
    if not _is_operational_admin(user, center):
        raise ValidationError(_('Only a center admin can connect the center\'s Telegram group.'),
                              code='telegram_not_center_admin')
    username = (client or TelegramClient()).username()
    code, expires_at = _new_code(user, center)
    return f'https://t.me/{username}?startgroup={code}', expires_at


@sensitive_variables('code')
def connect_group(code, chat_id, telegram_id):
    """
    Connect the group ``chat_id`` to the center of ``code``; return the center.

    ``telegram_id`` is the person who added the bot. Their account is linked at
    the same time when it is not linked yet and belongs to nobody else, so the
    center admin can answer from the group at once. Connecting another group
    replaces the center's previous one.

    Raises:
        ValidationError: ``telegram_link_invalid`` (unknown, used or expired
            code, or the user is no longer an active center admin of an
            operational center) or ``telegram_group_taken`` (the group serves
            another center).
    """
    User = get_user_model()
    with transaction.atomic():
        row = TelegramLinkCode.objects.usable().select_for_update().select_related('user', 'center').filter(
            code_hash=code_hash(code), center__isnull=False).first()
        if row is None or not _is_operational_admin(row.user, row.center):
            raise ValidationError(_('This link is invalid or expired. Ask for a new one.'),
                                  code='telegram_link_invalid')
        center = Center.objects.select_for_update().get(pk=row.center_id)
        if Center.objects.filter(telegram_chat_id=chat_id).exclude(pk=center.pk).exists():
            raise ValidationError(_('This Telegram group is already connected to another center.'),
                                  code='telegram_group_taken')
        center.telegram_chat_id = chat_id
        center.save(update_fields=['telegram_chat_id', 'updated_at'])
        user = row.user
        if user.telegram_chat_id is None and not User.objects.filter(telegram_chat_id=telegram_id).exists():
            user.telegram_chat_id = telegram_id
            user.save(update_fields=['telegram_chat_id', 'updated_at'])
        row.used_at = timezone.now()
        row.save(update_fields=['used_at', 'updated_at'])
    return center


def disconnect_center(center, user, client=None):
    """
    Disconnect ``center``'s Telegram group on behalf of ``user``; return the center.

    The group is cleared first, so the center is disconnected even when Telegram
    cannot be reached; then, after the commit, the bot posts a goodbye in the
    group and leaves it (failures are logged). Disconnecting a center without a
    group does nothing.

    Raises:
        ValidationError: ``telegram_not_center_admin`` unless ``user`` is an
            active center admin of the operational ``center``.
    """
    if not _is_operational_admin(user, center):
        raise ValidationError(_('Only a center admin can disconnect the center\'s Telegram group.'),
                              code='telegram_not_center_admin')
    with transaction.atomic():
        locked = Center.objects.select_for_update().get(pk=center.pk)
        old_chat_id = locked.telegram_chat_id
        if old_chat_id is None:
            return locked
        locked.telegram_chat_id = None
        locked.save(update_fields=['telegram_chat_id', 'updated_at'])
        transaction.on_commit(lambda: _leave_group(client or TelegramClient(), locked, old_chat_id))
    return locked


def _leave_group(client, center, chat_id):
    """Say goodbye in the old group and leave it; best effort, the center is already disconnected."""
    if not client.enabled:
        return
    with translation.override(notice_language(center)):
        text = gettext('This group is no longer connected to %(center)s. Referred questions will no longer '
                       'arrive here.') % {'center': center.name}
    try:
        client.send_message(chat_id, text)
        client.leave_chat(chat_id)
    except TelegramError as error:
        logger.warning('Leaving the Telegram group of center %s failed: %s', center.slug, error)


def disconnect_group(chat_id):
    """Forget the group ``chat_id`` (the bot was removed from it); return the number of centers changed."""
    return Center.objects.filter(telegram_chat_id=chat_id).update(telegram_chat_id=None, updated_at=timezone.now())


def move_group(old_chat_id, new_chat_id):
    """Follow a group upgraded to a supergroup, which changes its ID; return the number of centers changed."""
    return Center.objects.filter(telegram_chat_id=old_chat_id).update(telegram_chat_id=new_chat_id,
                                                                     updated_at=timezone.now())


def _is_operational_admin(user, center):
    """True when ``user`` is active and an active center admin of ``center``, itself operational."""
    return user.is_active and center.is_operational and (
        Membership.objects.for_center(center).active().center_admins().filter(user=user).exists())


@sensitive_variables('code')
def _new_code(user, center=None):
    """Store the hash of a new code for ``user`` (and ``center`` for a group link); return ``(code, expires_at)``."""
    # 16 bytes: 22 URL-safe characters, within Telegram's 64-character start parameter
    code = secrets.token_urlsafe(16)
    expires_at = timezone.now() + timedelta(minutes=LINK_MINUTES)
    TelegramLinkCode.objects.create(user=user, center=center, code_hash=code_hash(code), expires_at=expires_at)
    return code, expires_at


@sensitive_variables('code')
def link_account(code, telegram_id):
    """
    Link the Telegram account ``telegram_id`` to the user of ``code``; return the user.

    The code is used once. Linking again replaces the user's previous Telegram account.

    Raises:
        ValidationError: ``telegram_link_invalid`` (unknown, used or expired code,
            or deactivated user) or ``telegram_already_linked`` (this Telegram
            account belongs to another user).
    """
    User = get_user_model()
    with transaction.atomic():
        row = TelegramLinkCode.objects.usable().select_for_update().select_related('user').filter(
            code_hash=code_hash(code), center__isnull=True).first()
        if row is None or not row.user.is_active:
            raise ValidationError(_('This link is invalid or expired. Ask for a new one.'),
                                  code='telegram_link_invalid')
        if User.objects.filter(telegram_chat_id=telegram_id).exclude(pk=row.user_id).exists():
            raise ValidationError(_('This Telegram account is already linked to another account.'),
                                  code='telegram_already_linked')
        now = timezone.now()
        user = row.user
        user.telegram_chat_id = telegram_id
        user.save(update_fields=['telegram_chat_id', 'updated_at'])
        row.used_at = now
        row.save(update_fields=['used_at', 'updated_at'])
    return user
