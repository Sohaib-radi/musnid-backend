"""
Revising answers (ADR 0020) and handling referrals (ADR 0021).

Every channel (admin, center dashboard API, Telegram) goes through these
functions, so the rules hold everywhere. Rule violations raise
``ValidationError`` with a code, as in ``core.services``.

A referral is the ticket of a question the AI referred: ``open_referral``
creates it, ``assign`` gives it to a specialist, ``close`` ends it without an
answer, and ``revise`` marks it answered.
"""

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import Membership
from qa.models import AnswerRevision, Question, Referral
from qa.signals import referral_answered, referral_opened

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
    other, and the newest one is unambiguous. A referral of the question that is
    not yet answered is marked answered, whatever the reason: the asker now sees
    a specialist's text. A closed referral answered later becomes answered too.

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
        revision = AnswerRevision.objects.create(question=locked, author=author, text=text, reason=reason,
                                                 note=(note or '').strip())
        now = timezone.now()
        newly_answered = Referral.objects.filter(question=locked).exclude(status=Referral.Status.ANSWERED).update(
            status=Referral.Status.ANSWERED, answered_at=now, updated_at=now)
        if newly_answered:
            # Channels (Telegram) close the question for the other specialists
            referral = Referral.objects.get(question=locked)
            transaction.on_commit(lambda: referral_answered.send_robust(
                sender=Referral, referral=referral, author=author))
        return revision


#: Decisions after which the asker may send the question to the specialists
REFERABLE_DECISIONS = ('refer', 'abstain')


def can_request_specialist(question):
    """True when the AI did not answer ``question`` and it was not sent to the specialists yet."""
    interaction = getattr(question, 'interaction', None)
    return (interaction is not None and interaction.decision in REFERABLE_DECISIONS
            and not Referral.objects.filter(question=question).exists())


def referral_reason(interaction):
    """Why the AI did not answer: a personal ruling (level D), otherwise sources that do not cover it."""
    return Referral.Reason.LEVEL_D if interaction.level == 'D' else Referral.Reason.NO_EVIDENCE


def request_specialist(question, mode):
    """
    Send ``question`` to its center's specialists at the asker's request; return the referral.

    ``mode`` is ``Referral.Mode``: ``live`` (the asker waits; specialists have
    ``REFERRAL_LIVE_SECONDS`` to answer at once) or ``ticket`` (answered later).
    Both notify the specialists. The caller checks that the requester owns the question.

    Raises:
        ValidationError: ``not_referable`` (the AI answered it, or it was not
            saved), ``referral_exists`` (already sent) or ``invalid_mode``.
    """
    if mode not in Referral.Mode.values:
        raise ValidationError(_('Choose to ask a specialist now or to save a ticket.'), code='invalid_mode')
    with transaction.atomic():
        locked = Question.objects.select_for_update().get(pk=question.pk)
        interaction = getattr(locked, 'interaction', None)
        if interaction is None or interaction.decision not in REFERABLE_DECISIONS:
            raise ValidationError(_('This question was answered; it cannot be sent to a specialist.'),
                                  code='not_referable')
        if Referral.objects.filter(question=locked).exists():
            raise ValidationError(_('This question was already sent to the specialists.'), code='referral_exists')
        return open_referral(locked, referral_reason(interaction), mode)


def open_referral(question, reason, mode=Referral.Mode.LIVE):
    """
    Open the referral of ``question``, owned by the question's center; return it.

    Called by ``request_specialist`` once the asker chose to send the question.
    ``reason`` is a ``Referral.Reason`` value, chosen by code, never by the asker.
    A live referral gets ``live_until``, ``settings.REFERRAL_LIVE_SECONDS`` ahead
    (the live window); a ticket has none.
    Once that transaction commits, ``referral_opened`` is sent (``send_robust``:
    a failing receiver, such as the Telegram notice, never fails the question).
    """
    live_until = None
    if mode == Referral.Mode.LIVE:
        live_until = timezone.now() + timedelta(seconds=settings.REFERRAL_LIVE_SECONDS)
    referral = Referral.objects.create(question=question, center=question.center, reason=reason, mode=mode,
                                       live_until=live_until)
    transaction.on_commit(lambda: referral_opened.send_robust(sender=Referral, referral=referral))
    return referral


def assign(referral, user, assignee):
    """
    Give ``referral`` to ``assignee``, on behalf of ``user``; return the updated referral.

    ``user`` must be allowed to revise the question (``can_revise``), and
    ``assignee`` must be an active member of the referral's center. A specialist
    takes a ticket by assigning it to themselves; reassigning a ticket in
    progress is allowed. The status becomes ``in_progress``.

    Raises:
        ValidationError: ``referral_not_allowed``, ``referral_not_pending`` or
            ``referral_assignee_invalid``.
    """
    _check_can_handle(user, referral)
    is_member = Membership.objects.for_center(referral.center).active().filter(user=assignee).exists()
    if not (assignee.is_active and is_member):
        raise ValidationError(_('Assign the referral to an active member of its center.'),
                              code='referral_assignee_invalid')
    with transaction.atomic():
        locked = _lock_pending(referral)
        locked.assigned_to = assignee
        locked.status = Referral.Status.IN_PROGRESS
        locked.save(update_fields=['assigned_to', 'status', 'updated_at'])
    return locked


def close(referral, user, note):
    """
    Close ``referral`` without an answer, on behalf of ``user``; return the updated referral.

    The note says why (a duplicate, an abusive question, ...). It is kept for
    the center and staff, never shown to the asker.

    Raises:
        ValidationError: ``referral_not_allowed``, ``referral_note_required``
            or ``referral_not_pending``.
    """
    _check_can_handle(user, referral)
    note = (note or '').strip()
    if not note:
        raise ValidationError(_('Write why the referral is closed without an answer.'),
                              code='referral_note_required')
    with transaction.atomic():
        locked = _lock_pending(referral)
        locked.status = Referral.Status.CLOSED
        locked.closed_at = timezone.now()
        locked.close_note = note
        locked.save(update_fields=['status', 'closed_at', 'close_note', 'updated_at'])
    return locked


def _check_can_handle(user, referral):
    """Refuse users who may not revise the referred question: they may not handle its ticket either."""
    if not can_revise(user, referral.question):
        raise ValidationError(_('You cannot handle referrals of this center.'), code='referral_not_allowed')


def _lock_pending(referral):
    """Lock the referral's row and return it, refusing a ticket already answered or closed."""
    locked = Referral.objects.select_for_update().get(pk=referral.pk)
    if not locked.is_pending:
        raise ValidationError(_('This referral is already answered or closed.'), code='referral_not_pending')
    return locked
