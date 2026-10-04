"""
Fixed, translated replies and answer notes (ADR 0016, ADR 0017).

Decisions and fixed replies are code, never generated. This module does not import
CrewAI, so the API can build notes and the daily-limit reply without loading the flow.
"""

from django.utils import translation
from django.utils.translation import gettext as _

REPLY_LANGUAGES = {'ar', 'en', 'fr'}

# Note codes sent to clients, which style notes by code; mapped to the fixed reply kind.
NOTE_KINDS = {'partial': 'partial', 'level_c': 'disagreement'}


def fixed_reply(kind, language):
    """
    A fixed reply in ``language`` (English for any other language).

    ``kind``: out_of_scope, refer, abstain, partial, disagreement, daily_capacity.
    """
    with translation.override(language if language in REPLY_LANGUAGES else 'en'):
        return {
            'out_of_scope': _('This service only answers questions about Islam. '
                              'Please ask a question about Islam.'),
            'refer': _('Your question needs a specialist. It has been referred to a center of '
                       'specialists, who will answer you.'),
            'abstain': _('We could not find an answer to this question in our sources. '
                         'Please rephrase it or ask a center of specialists.'),
            'partial': _('Note: our sources answer this question only in part.'),
            'disagreement': _('This matter involves scholarly disagreement; consult a specialist '
                              'for your situation.'),
            'daily_capacity': _('The service has reached its limit of questions for today. '
                                'Please try again tomorrow.'),
        }[kind]


def note_codes(decision, level):
    """
    The codes of the notes that follow an answer, in display order.

    ``partial`` for a partial answer; ``level_c`` for an answer to a level-C question
    (scholarly disagreement). Fixed replies (refer, abstain, out of scope) have none.
    """
    if decision not in ('answer', 'partial'):
        return []
    codes = []
    if decision == 'partial':
        codes.append('partial')
    if level == 'C':
        codes.append('level_c')
    return codes


def notes(decision, level, language):
    """The notes of an answer as ``[{'code', 'text'}]``, text in ``language``."""
    return [{'code': code, 'text': fixed_reply(NOTE_KINDS[code], language)}
            for code in note_codes(decision, level)]
