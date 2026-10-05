"""
Revising answers (ADR 0020): the rules for who may change what the asker sees.

Every channel (admin, center dashboard API, Telegram) goes through ``revise``,
so the rules hold everywhere. Rule violations raise ``ValidationError`` with a
code, as in ``core.services``.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from core.models import Membership
from qa.models import AnswerRevision, Question

#: Longest revision accepted; a few pages of text, far above any answer measured so far
TEXT_MAX = 10000


def can_revise(user, question):
    """
    Whether ``user`` may revise the answer of ``question``.

    Allowed: staff with the ``qa.add_answerrevision`` permission (superusers
    included), and active members (specialist or center admin) of the question's
    center while that center is operational (approved and active).
    """
    if not user.is_active:
        return False
    if user.is_staff and user.has_perm('qa.add_answerrevision'):
        return True
    return question.center.is_operational and (
        Membership.objects.for_center(question.center).active().filter(user=user).exists()
    )


def revise(question, author, text, reason, note=''):
    """
    Add a revision of ``question``'s answer, written by ``author``; return it.

    The question row is locked so concurrent revisions are saved one after the
    other, and the newest one is unambiguous.

    Raises:
        ValidationError: ``revision_not_allowed``, ``revision_text_required``,
            ``revision_text_too_long`` or ``revision_reason_invalid``.
    """
    if not can_revise(author, question):
        raise ValidationError(_('You cannot revise answers of this center.'), code='revision_not_allowed')
    text = (text or '').strip()
    if not text:
        raise ValidationError(_('Write the answer the asker should see.'), code='revision_text_required')
    if len(text) > TEXT_MAX:
        raise ValidationError(_('The answer is limited to %(max)d characters.'), code='revision_text_too_long',
                              params={'max': TEXT_MAX})
    if reason not in AnswerRevision.Reason.values:
        raise ValidationError(_('Choose why the answer is revised.'), code='revision_reason_invalid')
    with transaction.atomic():
        locked = Question.objects.select_for_update().get(pk=question.pk)
        return AnswerRevision.objects.create(question=locked, author=author, text=text, reason=reason,
                                             note=(note or '').strip())
