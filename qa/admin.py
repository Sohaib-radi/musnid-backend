"""
Read-only admin for asked questions and how the AI answered them.

A question's page shows its ``Interaction``: the answer, each kept sentence with
its supporting quote and Bayyinat source, and each sentence the checks removed.
Questions and interactions are never added, changed or deleted here: questions
come from the ask API, and an interaction is the audit record of one answer.

Changing what the asker sees is a revision (ADR 0020): the "Revise the answer"
page saves one through ``qa.services.revise``, and the page lists every revision,
read-only.
"""

import re
import uuid

from django.contrib import admin, messages
from django.contrib.admin.utils import unquote
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db.models import Exists, OuterRef
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join
from django.utils.text import Truncator
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display

from qa import services
from qa.models import AnswerRevision, Interaction, Question
from qa.services import TEXT_MAX

#: Badge colour of each decision, from served (green) to not answered (red)
DECISION_COLORS = {
    Interaction.Decision.ANSWER: 'success',
    Interaction.Decision.PARTIAL: 'info',
    Interaction.Decision.REFER: 'warning',
    Interaction.Decision.ABSTAIN: 'danger',
    Interaction.Decision.OUT_OF_SCOPE: 'danger',
}

#: Why the verification removed a sentence (``Interaction.dropped[].reason``)
DROP_REASONS = {
    'quote': _('Quote not found in the sources'),
    'entailment': _('Quote does not support the sentence'),
}


def interaction_of(question):
    """The question's interaction, or ``None`` when the answer was never saved."""
    try:
        return question.interaction
    except ObjectDoesNotExist:
        return None


class AnswerRevisionInline(TabularInline):
    """Every revision of the answer, newest first; read-only, added through ``revise``."""

    model = AnswerRevision
    extra = 0
    fields = ['created_at', 'author', 'reason', 'text', 'note']
    readonly_fields = fields
    ordering = ['-created_at']
    verbose_name_plural = _('Revisions shown to the asker (newest first)')

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Question)
class QuestionAdmin(ModelAdmin):
    """Questions with their decision; each page shows the full AI answer and its checks."""

    list_display = ['short_text', 'asked_by', 'lang', 'decision', 'answered_by', 'level', 'latency', 'tokens', 'has_error', 'center',
                    'created_at']
    list_filter = ['interaction__decision', 'interaction__level', 'lang', 'center']
    search_fields = ['text', 'asker__email']
    search_help_text = _('Search by question text or asker email, or paste a follow-up number.')
    list_select_related = ['center', 'interaction', 'asker']
    date_hierarchy = 'created_at'
    # Explain the columns and sections to first-time readers, such as the competition jury
    list_before_template = 'admin/qa/question/list_help.html'
    change_form_before_template = 'admin/qa/question/change_help.html'
    fieldsets = [
        (_('Question'), {'fields': ['text', 'uuid', 'asked_by', 'lang', 'center', 'session_id', 'created_at']}),
        (_('Answer'), {'fields': ['decision', 'level', 'answer', 'kept_sentences', 'dropped_sentences']}),
        (_('Retrieval'), {'fields': ['search_query', 'retrieved'], 'classes': ['collapse']}),
        (_('Run'), {
            'fields': ['model_used', 'latency', 'tokens', 'error'],
            'classes': ['collapse'],
        }),
    ]
    inlines = [AnswerRevisionInline]
    readonly_fields = [
        'text', 'uuid', 'asked_by', 'lang', 'center', 'session_id', 'created_at',
        'decision', 'level', 'answer', 'kept_sentences', 'dropped_sentences',
        'search_query', 'retrieved', 'model_used', 'latency', 'tokens', 'error',
    ]

    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        """Flag revised questions in one query, for the "Answered by" column."""
        return super().get_queryset(request).annotate(
            revised=Exists(AnswerRevision.objects.filter(question=OuterRef('pk'))))

    def get_urls(self):
        return [
            path('<path:object_id>/revise/', self.admin_site.admin_view(self.revise_view), name='qa_question_revise'),
            *super().get_urls(),
        ]

    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Offer "Revise the answer" to users allowed to revise this question."""
        question = self.get_object(request, unquote(object_id))
        extra_context = extra_context or {}
        if question is not None and services.can_revise(request.user, question):
            extra_context['revise_url'] = reverse('admin:qa_question_revise', args=[question.pk])
        return super().change_view(request, object_id, form_url, extra_context)

    def revise_view(self, request, object_id):
        """GET: the revision form, prefilled with what the asker sees now. POST: save it through ``revise``."""
        question = get_object_or_404(Question.objects.with_answers(), pk=unquote(object_id))
        if not services.can_revise(request.user, question):
            raise PermissionDenied
        current = question.latest_revision()
        interaction = interaction_of(question)
        # A question the AI did not answer gets a specialist's answer; otherwise the reason is chosen
        unanswered = current is None and (interaction is None or interaction.decision in ('refer', 'abstain'))
        values = {
            'text': current.text if current else self._plain_answer(question),
            'reason': AnswerRevision.Reason.SPECIALIST_ANSWER if unanswered else '',
            'note': '',
        }
        error = None
        if request.method == 'POST':
            values = {key: request.POST.get(key, '') for key in values}
            try:
                services.revise(question, request.user, values['text'], values['reason'], values['note'])
            except ValidationError as caught:
                error = ' '.join(caught.messages)
            else:
                self.message_user(request, _('The revised answer is now shown to the asker.'), messages.SUCCESS)
                return HttpResponseRedirect(reverse('admin:qa_question_change', args=[question.pk]))
        return TemplateResponse(request, 'admin/qa/question/revise.html', {
            **self.admin_site.each_context(request),
            'title': _('Revise the answer'),
            'opts': self.model._meta,
            'original': question,
            'question': question,
            'current': current,
            'values': values,
            'error': error,
            'reasons': AnswerRevision.Reason.choices,
            'text_max': TEXT_MAX,
            'change_url': reverse('admin:qa_question_change', args=[question.pk]),
        })

    @staticmethod
    def _plain_answer(question):
        """The AI answer without its ``[Q<n>]`` markers: a starting point for the specialist."""
        interaction = interaction_of(question)
        if interaction is None:
            return ''
        if interaction.sentences:
            return ' '.join(sentence.get('text', '') for sentence in interaction.sentences)
        return re.sub(r'\s*\[Q\d+\]', '', interaction.answer_text)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_search_results(self, request, queryset, search_term):
        """Also find a question by its exact follow-up number (``uuid``)."""
        results, may_have_duplicates = super().get_search_results(request, queryset, search_term)
        try:
            follow_up = uuid.UUID(search_term.strip())
        except ValueError:
            return results, may_have_duplicates
        return results | queryset.filter(uuid=follow_up), may_have_duplicates

    @display(description=_('question'))
    def short_text(self, question):
        return Truncator(question.text).chars(90)

    @display(description=_('asker'), ordering='asker__email')
    def asked_by(self, question):
        """The account's email when the asker was logged in, otherwise "Anonymous"."""
        return question.asker.email if question.asker else _('Anonymous')

    @display(description=_('decision'), ordering='interaction__decision', label=DECISION_COLORS)
    def decision(self, question):
        interaction = interaction_of(question)
        if interaction is None:
            return '-'
        return interaction.decision, interaction.get_decision_display()

    @display(description=_('answered by'), ordering='revised', label={'ai': 'info', 'center': 'success'})
    def answered_by(self, question):
        """AI until a specialist revises the answer, then Center: what the asker sees now."""
        if getattr(question, 'revised', False):
            return 'center', _('Center')
        return 'ai', _('AI')

    @display(description=_('level'), ordering='interaction__level')
    def level(self, question):
        interaction = interaction_of(question)
        return interaction.get_level_display() if interaction and interaction.level else '-'

    @display(description=_('answer'))
    def answer(self, question):
        interaction = interaction_of(question)
        if interaction is None:
            return _('No answer was saved for this question.')
        return format_html('<div dir="auto" class="musnid-answer">{}</div>', interaction.answer_text)

    @display(description=_('kept sentences'))
    def kept_sentences(self, question):
        """Each sentence the asker saw, with the quote that supports it and its source question."""
        interaction = interaction_of(question)
        if interaction is None or not interaction.sentences:
            return '-'
        return format_html('<ol class="musnid-sentences">{}</ol>', format_html_join(
            '', '<li><div dir="auto">{}</div><blockquote dir="rtl" lang="ar" class="musnid-quote">{}</blockquote>'
                '<div class="musnid-meta">{}</div></li>',
            ((s.get('text', ''), s.get('quote', ''), _('Bayyinat question %(number)s') % {'number': s.get('number')})
             for s in interaction.sentences),
        ))

    @display(description=_('removed sentences'))
    def dropped_sentences(self, question):
        """Sentences the verification removed before the answer was shown, with the reason."""
        interaction = interaction_of(question)
        if interaction is None or not interaction.dropped:
            return '-'
        return format_html('<ol class="musnid-sentences">{}</ol>', format_html_join(
            '', '<li><div dir="auto">{}</div><blockquote dir="rtl" lang="ar" class="musnid-quote">{}</blockquote>'
                '<div class="musnid-removed-reason">{}</div></li>',
            ((d.get('text', ''), d.get('quote', ''), DROP_REASONS.get(d.get('reason'), d.get('reason', '')))
             for d in interaction.dropped),
        ))

    @display(description=_('search query'))
    def search_query(self, question):
        interaction = interaction_of(question)
        return interaction.search_query if interaction and interaction.search_query else '-'

    @display(description=_('retrieved'))
    def retrieved(self, question):
        """The ranked search results: Bayyinat question, chunk kind and score."""
        interaction = interaction_of(question)
        if interaction is None or not interaction.retrieved:
            return '-'
        return format_html('<ol class="musnid-sentences musnid-compact">{}</ol>', format_html_join(
            '', '<li>{} · {} · {}</li>',
            ((_('Bayyinat question %(number)s') % {'number': r.get('question_number')}, r.get('kind', ''),
              r.get('score', '')) for r in interaction.retrieved),
        ))

    # Not "model": ModelAdmin.model is the admin's model class
    @display(description=_('model'))
    def model_used(self, question):
        interaction = interaction_of(question)
        if interaction is None:
            return '-'
        return f'{interaction.model_name} ({interaction.prompt_version})' if interaction.prompt_version \
            else interaction.model_name or '-'

    @display(description=_('response time'), ordering='interaction__latency_ms')
    def latency(self, question):
        interaction = interaction_of(question)
        return _('%(seconds).1f s') % {'seconds': interaction.latency_ms / 1000} if interaction else '-'

    @display(description=_('tokens'), ordering='interaction__tokens_in')
    def tokens(self, question):
        interaction = interaction_of(question)
        if interaction is None:
            return '-'
        return _('%(input)s in, %(output)s out') % {'input': interaction.tokens_in, 'output': interaction.tokens_out}

    @display(description=_('error'))
    def error(self, question):
        interaction = interaction_of(question)
        if interaction is None or not interaction.error:
            return '-'
        return format_html('<pre class="musnid-pre">{}</pre>', interaction.error)

    @display(description=_('error'), label={'yes': 'danger', 'no': 'success'})
    def has_error(self, question):
        """Yes when a step of the run failed (details on the question's page), No otherwise."""
        interaction = interaction_of(question)
        if interaction is None:
            return '-'
        return ('yes', _('Yes')) if interaction.error else ('no', _('No'))
