"""
Set the bot's profile in Arabic, English and French (ADR 0023): the description
shown in an empty chat before Start, the short description on its profile, and
its command list. Run once per bot, and again after changing the texts.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import translation
from django.utils.translation import gettext as _

from agents.replies import REPLY_LANGUAGES
from telegram_bot.client import TelegramClient, TelegramError


def profile_texts():
    """The texts of the bot's profile, translated in the active language."""
    return {
        # Telegram limits: description 512 characters, short description 120
        'description': _('Musnid connects people who ask about Islam with centers of specialists. Specialists '
                         'receive here the questions that need them, and answer in one tap.'),
        'short_description': _('Questions about Islam, answered by centers of specialists.'),
        'start': _('Start or show the welcome message'),
    }


class Command(BaseCommand):
    help = "Set the bot's description, short description and commands in Arabic, English and French."

    def handle(self, *args, **options):
        client = TelegramClient()
        if not client.enabled:
            raise CommandError('TELEGRAM_BOT_TOKEN is not set.')
        try:
            # No language_code: the default, shown to users of any other language
            for language in [None, *sorted(REPLY_LANGUAGES)]:
                with translation.override(language or 'en'):
                    texts = profile_texts()
                scope = {'language_code': language} if language else {}
                client.call('setMyDescription', description=texts['description'], **scope)
                client.call('setMyShortDescription', short_description=texts['short_description'], **scope)
                client.call('setMyCommands', commands=[{'command': 'start', 'description': texts['start']}], **scope)
                self.stdout.write(f'Profile set: {language or "default"}')
        except TelegramError as error:
            raise CommandError(str(error)) from None
