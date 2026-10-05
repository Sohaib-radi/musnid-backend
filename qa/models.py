"""
Questions and how they were answered, kept for review and future fine-tuning.

Asking needs no account: an anonymous asker is known only by ``session_id``, an
opaque string. A logged-in asker's questions are also linked to their account
(``Question.asker``), so they can find them from any device (ADR 0019). Stored
errors have API keys masked.
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
