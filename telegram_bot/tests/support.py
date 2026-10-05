"""A fake ``TelegramClient`` for tests: records messages, or fails like Telegram."""

from telegram_bot.client import TelegramError


class FakeClient:
    """Records sent messages; ``error`` makes every send fail with it."""

    def __init__(self, enabled=True, error=None):
        self.enabled = enabled
        self.error = error
        self.sent = []

    def send_message(self, chat_id, text):
        if self.error:
            raise TelegramError(self.error)
        self.sent.append((chat_id, text))
        return {'message_id': 100 + len(self.sent)}
