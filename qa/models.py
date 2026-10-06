"""
Questions and how they were answered, kept for review and future fine-tuning.

Asking needs no account: an anonymous asker is known only by ``session_id``, an
opaque string. A logged-in asker's questions are also linked to their account
(``Question.asker``), so they can find them from any device (ADR 0019). Stored
errors have API keys masked.

A specialist can revise an answer (``AnswerRevision``, ADR 0020): the asker then
sees the latest revision instead of the AI's answer, which stays untouched in
``Interaction`` as the audit record.

A question the AI refers opens a ``Referral`` (ADR 0021): the ticket a center of
specialists works through, from open to answered or closed.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import BaseModel, CenterLinkedModel
from core.models.base import CenterQuerySet


class QuestionQuerySet(CenterQuerySet):
    """Queries on questions: by session or asker (history) and by day (global daily limit)."""

    def for_session(self, session_id):
        """The questions of one anonymous session, newest first."""
        return self.filter(session_id=session_id).order_by('-created_at')

    def for_asker(self, user):
        """The questions a logged-in user asked, from any device, newest first."""
        return self.filter(asker=user).order_by('-created_at')

    def with_answers(self):
        """Load what the public payload needs in two queries: interaction, center and referral; revisions."""
        return self.select_related('interaction', 'center', 'referral').prefetch_related('revisions')

    def asked_today(self):
        """Questions created since 00:00 UTC today, across all centers."""
        start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.filter(created_at__gte=start)


class Question(BaseModel, CenterLinkedModel):
    """
    A question, owned by the center it is routed to, and by its asker when logged in.

    ``uuid`` is the public identifier, and also the follow-up number given to the
    asker when the question is referred to a center.
    """

    uuid = models.UUIDField(_('public identifier'), default=uuid.uuid4, unique=True, editable=False)
    text = models.TextField(_('text'))
    lang = models.CharField(_('language'), max_length=5, blank=True)
    session_id = models.CharField(_('session'), max_length=64, blank=True, db_index=True)
    translations = models.JSONField(
        _('translations'), default=dict, blank=True,
        help_text=_('Machine translations of the question for specialists, by language code.'))
    # SET_NULL: deleting an account keeps its questions (answers, reviews), now anonymous
    asker = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='questions',
        verbose_name=_('asker'), help_text=_('The account that asked, when logged in. Empty for anonymous askers.'),
    )

    objects = QuestionQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        verbose_name = _('question')
        verbose_name_plural = _('questions')
        indexes = [
            models.Index(fields=['session_id', '-created_at'], name='question_session_recent'),
            models.Index(fields=['asker', '-created_at'], name='question_asker_recent'),
        ]

    def __str__(self):
        return self.text[:80]

    def latest_revision(self):
        """The newest ``AnswerRevision``, or ``None`` when the AI's answer was never revised.

        Reads ``revisions.all()`` so a ``prefetch_related('revisions')`` (see
        ``QuestionQuerySet.with_answers``) is used instead of one query per question.
        """
        revisions = list(self.revisions.all())
        return max(revisions, key=lambda revision: revision.created_at) if revisions else None


class Interaction(BaseModel):
    """The full trace of answering one question: routing, retrieval, answer, verdict."""

    class Level(models.TextChoices):
        """Difficulty level set by the classifier."""

        A = 'A', 'A'
        B = 'B', 'B'
        C = 'C', 'C'
        D = 'D', 'D'
        OUT_OF_SCOPE = 'out_of_scope', _('Out of scope')

    class Decision(models.TextChoices):
        """What was returned to the asker."""

        ANSWER = 'answer', _('Answer')
        PARTIAL = 'partial', _('Partial answer')
        ABSTAIN = 'abstain', _('Abstain')
        REFER = 'refer', _('Referred to a center')
        OUT_OF_SCOPE = 'out_of_scope', _('Out of scope')

    question = models.OneToOneField(
        Question, on_delete=models.CASCADE, related_name='interaction', verbose_name=_('question'),
    )
    level = models.CharField(_('level'), max_length=12, choices=Level.choices, null=True, blank=True)
    search_query = models.TextField(_('search query'), blank=True)
    retrieved = models.JSONField(_('retrieved'), default=list, blank=True,
                                 help_text=_('Ranked results: question number, score, chunk kind.'))
    evidence_question_numbers = models.JSONField(_('evidence question numbers'), default=list, blank=True)
    # Kept so each answer can be rebuilt exactly as the writer saw it, e.g. for a
    # fine-tuning dataset, even after the books are re-imported (empty before 2026-10-06)
    evidence = models.TextField(
        _('evidence given to the writer'), blank=True,
        help_text=_('The exact evidence text the writer received; empty for fixed replies.'))
    answer_text = models.TextField(_('answer'), blank=True)
    citations = models.JSONField(_('citations'), default=list, blank=True)
    sentences = models.JSONField(
        _('sentences'), default=list, blank=True,
        help_text=_('Kept sentences: text without citation markers, supporting quote, source question number.'))
    dropped = models.JSONField(
        _('dropped sentences'), default=list, blank=True,
        help_text=_('Sentences removed by the quote or entailment check: text, quote, reason.'))
    decision = models.CharField(_('decision'), max_length=12, choices=Decision.choices)
    verifier_verdict = models.CharField(_('verifier verdict'), max_length=10, blank=True)
    model_name = models.CharField(_('model'), max_length=100, blank=True)
    prompt_version = models.CharField(_('prompt version'), max_length=20, blank=True)
    latency_ms = models.PositiveIntegerField(_('latency (ms)'), default=0)
    tokens_in = models.PositiveIntegerField(_('input tokens'), default=0)
    tokens_out = models.PositiveIntegerField(_('output tokens'), default=0)
    error = models.TextField(_('error'), blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = _('interaction')
        verbose_name_plural = _('interactions')

    def __str__(self):
        return f'{self.decision}: {self.question}'


class HumanLabel(BaseModel):
    """A reviewer's judgement of an interaction, for evaluation and fine-tuning."""

    class Verdict(models.TextChoices):
        """Reviewer verdict."""

        APPROVE = 'approve', _('Approve')
        CORRECT = 'correct', _('Correct')
        REJECT = 'reject', _('Reject')

    interaction = models.ForeignKey(
        Interaction, on_delete=models.CASCADE, related_name='labels', verbose_name=_('interaction'),
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
        verbose_name=_('reviewer'),
    )
    verdict = models.CharField(_('verdict'), max_length=10, choices=Verdict.choices)
    corrected_answer = models.TextField(_('corrected answer'), blank=True)
    reason = models.TextField(_('reason'), blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = _('human label')
        verbose_name_plural = _('human labels')

    def __str__(self):
        return f'{self.verdict}: {self.interaction_id}'


class AnswerRevision(BaseModel):
    """
    A version of an answer written by a person, shown to the asker instead of the AI's.

    Revisions are never edited: each change adds one, so the history keeps who
    changed what, when and why. Created only through ``qa.services.revise``.
    The asker sees the text and the center's name, never the author or the note.
    """

    class Reason(models.TextChoices):
        """Why the answer was revised."""

        CORRECTION = 'correction', _('Correction of an error')
        CLARIFICATION = 'clarification', _('Clarification or completion')
        SPECIALIST_ANSWER = 'specialist_answer', _('Answer by a specialist')

    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name='revisions', verbose_name=_('question'),
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
        verbose_name=_('author'),
    )
    text = models.TextField(_('answer'))
    reason = models.CharField(_('reason'), max_length=20, choices=Reason.choices)
    note = models.TextField(_('internal note'), blank=True,
                            help_text=_('For the center and staff only; never shown to the asker.'))

    class Meta(BaseModel.Meta):
        verbose_name = _('answer revision')
        verbose_name_plural = _('answer revisions')

    def __str__(self):
        return f'{self.get_reason_display()}: {self.question}'



class ReferralQuerySet(CenterQuerySet):
    """Queries on referrals: the center's queue and a specialist's own tickets."""

    def pending(self):
        """Referrals still waiting for an answer: open or in progress."""
        return self.filter(status__in=Referral.PENDING)

    def assigned_to(self, user):
        """The referrals assigned to ``user``."""
        return self.filter(assigned_to=user)


class Referral(BaseModel, CenterLinkedModel):
    """
    The ticket of a question the AI referred to a center of specialists (ADR 0021).

    Opened when the asker chooses to send a question the AI did not answer
    (``refer`` or ``abstain``) to the specialists, live or as a ticket
    (``qa.services.request_specialist``), and changed only through ``qa.services``
    (``assign``, ``close``, ``revise``): status and dates are never edited directly. The asker sees the status, never the assignee
    or the closing note.
    """

    class Reason(models.TextChoices):
        """Why the AI referred the question."""

        LEVEL_D = 'level_d', _('Personal ruling (level D)')
        NO_EVIDENCE = 'no_evidence', _('Not covered by the sources')

    class Status(models.TextChoices):
        """Where the ticket stands."""

        OPEN = 'open', _('Open')
        IN_PROGRESS = 'in_progress', _('In progress')
        ANSWERED = 'answered', _('Answered')
        CLOSED = 'closed', _('Closed without an answer')

    class Mode(models.TextChoices):
        """What the asker chose when sending the question to the specialists."""

        LIVE = 'live', _('Asked a specialist now')
        TICKET = 'ticket', _('Saved as a ticket')

    #: Statuses of a ticket still waiting for an answer
    PENDING = (Status.OPEN, Status.IN_PROGRESS)

    question = models.OneToOneField(
        Question, on_delete=models.CASCADE, related_name='referral', verbose_name=_('question'),
    )
    reason = models.CharField(_('reason'), max_length=12, choices=Reason.choices)
    status = models.CharField(_('status'), max_length=12, choices=Status.choices, default=Status.OPEN)
    mode = models.CharField(_('mode'), max_length=8, choices=Mode.choices, default=Mode.LIVE)
    # SET_NULL: offboarding or deleting an account must not delete the ticket
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_referrals', verbose_name=_('assigned to'),
    )
    # Until then the asker waits for a live answer; afterwards the ticket stays in the
    # center's queue (no background job: the deadline is only a date clients compare to)
    live_until = models.DateTimeField(
        _('live until'), null=True, blank=True,
        help_text=_('End of the live window in which specialists are expected to answer at once.'),
    )
    answered_at = models.DateTimeField(_('answered at'), null=True, blank=True)
    closed_at = models.DateTimeField(_('closed at'), null=True, blank=True)
    close_note = models.TextField(_('closing note'), blank=True,
                                  help_text=_('Why the center closed it without an answer; never shown to the asker.'))

    objects = ReferralQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        verbose_name = _('ticket')
        verbose_name_plural = _('tickets')
        indexes = [models.Index(fields=['center', 'status', '-created_at'], name='referral_center_queue')]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(status='answered') | models.Q(answered_at__isnull=False),
                name='referral_answered_has_date',
                violation_error_message=_('An answered referral needs the date of its answer.'),
            ),
            models.CheckConstraint(
                condition=~models.Q(status='closed') | models.Q(closed_at__isnull=False),
                name='referral_closed_has_date',
                violation_error_message=_('A closed referral needs the date it was closed.'),
            ),
        ]

    def __str__(self):
        return f'{self.get_status_display()}: {self.question}'

    @property
    def is_pending(self):
        """True while the ticket waits for an answer (open or in progress)."""
        return self.status in self.PENDING
