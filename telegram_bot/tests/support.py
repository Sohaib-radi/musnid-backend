"""A fake ``TelegramClient`` for tests: records messages, or fails like Telegram."""

from telegram_bot.client import TelegramError


class FakeClient:
    """Records sent messages, replies and groups left; ``error`` makes every call fail with it."""

    def __init__(self, enabled=True, error=None):
        self.enabled = enabled
        self.error = error
        self.sent = []
        self.replies = []
        self.left = []
        self.markups = []
        self.callbacks = []

    def send_message(self, chat_id, text, reply_markup=None):
        if self.error:
            raise TelegramError(self.error)
        self.sent.append((chat_id, text))
        self.markups.append(reply_markup)
        return {'message_id': 100 + len(self.sent)}

    def answer_callback(self, callback_id, text=''):
        self.callbacks.append((callback_id, text))
        return True

    def reply(self, chat_id, message_id, text):
        if self.error:
            raise TelegramError(self.error)
        self.replies.append((chat_id, message_id, text))
        return {'message_id': 500 + len(self.replies)}

    def leave_chat(self, chat_id):
        if self.error:
            raise TelegramError(self.error)
        self.left.append(chat_id)
        return True

    def username(self):
        return 'musnid_test_bot'
