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
    """
    A failed Bot API call. The message never contains the token.

    ``retryable`` is true for failures that may pass by themselves: network
    errors, unreadable replies, Telegram's own errors (5xx) and rate limits (429).
    A refusal such as a wrong token (401) or a webhook in the way (409) is not.
    """

    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.retryable = retryable


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
    def call(self, method, http_timeout=TIMEOUT, **params):
        """
        Call ``method`` with ``params`` (sent as JSON) and return its ``result``.

        ``http_timeout`` is how long to wait for the reply; long polling needs
        more than ``TIMEOUT``.

        Raises:
            TelegramError: on a network failure, an unreadable reply, or a reply
                with ``ok`` false.
        """
        url = f'{API}/bot{self._token}/{method}'
        try:
            with httpx.Client(timeout=http_timeout, transport=self._transport) as http:
                body = http.post(url, json=params).json()
        except (httpx.HTTPError, ValueError) as error:
            # from None: the chained exception would show the URL, hence the token
            raise TelegramError(f'{method}: {type(error).__name__}', retryable=True) from None
        if not body.get('ok'):
            code = body.get('error_code') or 0
            raise TelegramError(f'{method}: {body.get("error_code", "")} {body.get("description", "")}'.strip(),
                                retryable=code == 429 or code >= 500)
        return body['result']

    def send_message(self, chat_id, text):
        """Send ``text`` (Telegram HTML) to ``chat_id`` without link previews; return the sent message."""
        return self.call('sendMessage', chat_id=chat_id, text=text, parse_mode='HTML',
                         link_preview_options={'is_disabled': True})

    def reply(self, chat_id, message_id, text):
        """Send plain ``text`` to ``chat_id`` as a reply to ``message_id``; return the sent message."""
        return self.call('sendMessage', chat_id=chat_id, text=text,
                         reply_parameters={'message_id': message_id, 'allow_sending_without_reply': True})

    def get_updates(self, offset=None, wait=0):
        """
        The pending updates, only while no webhook is set.

        ``offset`` confirms every update before it; ``wait`` is the long-polling
        time in seconds (0 returns at once).
        """
        params = {'allowed_updates': ['message', 'my_chat_member'], 'timeout': wait}
        if offset is not None:
            params['offset'] = offset
        return self.call('getUpdates', http_timeout=wait + TIMEOUT, **params)

    def leave_chat(self, chat_id):
        """Make the bot leave ``chat_id``."""
        return self.call('leaveChat', chat_id=chat_id)

    def username(self):
        """The bot's username (``getMe``), used to build its t.me links."""
        return self.call('getMe')['username']
