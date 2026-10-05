"""
A minimal client of the Telegram Bot API over httpx (ADR 0022).

Only the methods the bot uses. The token is part of every request URL, so a
failure never shows the URL: ``TelegramError`` carries Telegram's own error
description, or only the exception type for a network failure.
"""

import httpx
from django.conf import settings
from django.views.decorators.debug import sensitive_variables

API = 'https://api.telegram.org'
#: Seconds to wait for Telegram; the notice is sent while the asker's request finishes
TIMEOUT = 5


class TelegramError(Exception):
    """A failed Bot API call. The message never contains the token."""


class TelegramClient:
    """
    Calls the Bot API with ``settings.TELEGRAM_BOT_TOKEN``.

    An empty token disables the bot (``enabled`` is false). ``transport`` lets
    tests pass an ``httpx.MockTransport`` instead of reaching Telegram.
    """

    def __init__(self, token=None, transport=None):
        self._token = settings.TELEGRAM_BOT_TOKEN if token is None else token
        self._transport = transport

    def __repr__(self):
        return f'<TelegramClient enabled={self.enabled}>'  # never the token

    @property
    def enabled(self):
        """True when a token is configured."""
        return bool(self._token)

    @sensitive_variables('url')
    def call(self, method, **params):
        """
        Call ``method`` with ``params`` (sent as JSON) and return its ``result``.

        Raises:
            TelegramError: on a network failure, an unreadable reply, or a reply
                with ``ok`` false.
        """
        url = f'{API}/bot{self._token}/{method}'
        try:
            with httpx.Client(timeout=TIMEOUT, transport=self._transport) as http:
                body = http.post(url, json=params).json()
        except (httpx.HTTPError, ValueError) as error:
            # from None: the chained exception would show the URL, hence the token
            raise TelegramError(f'{method}: {type(error).__name__}') from None
        if not body.get('ok'):
            raise TelegramError(f'{method}: {body.get("error_code", "")} {body.get("description", "")}'.strip())
        return body['result']

    def send_message(self, chat_id, text):
        """Send ``text`` (Telegram HTML) to ``chat_id`` without link previews; return the sent message."""
        return self.call('sendMessage', chat_id=chat_id, text=text, parse_mode='HTML',
                         link_preview_options={'is_disabled': True})

    def get_updates(self):
        """The pending updates (only while no webhook is set), to find the chats the bot was added to."""
        return self.call('getUpdates', allowed_updates=['message', 'my_chat_member'])
