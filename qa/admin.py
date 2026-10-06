"""
Read-only admin for asked questions and how the AI answered them.

A question's page shows its ``Interaction``: the answer, each kept sentence with
its supporting quote and Bayyinat source, and each sentence the checks removed.
Questions and interactions are never added, changed or deleted here: questions
come from the ask API, and an interaction is the audit record of one answer.

Changing what the asker sees is a revision (ADR 0020): the "Revise the answer"
page saves one through ``qa.services.revise``, and the page lists every revision,
read-only.

Referrals (ADR 0021) are the tickets of referred questions: a read-only list per
status, with actions that call ``qa.services.assign`` and ``qa.services.close``.
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
from django.utils.translation import ngettext
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action, display
from unfold.sections import TemplateSection

from qa import services
from qa.models import AnswerRevision, HumanLabel, Interaction, Question, Referral
from qa.services import TEXT_MAX

#: Badge colour of each decision, from served (green) to not answered (red)
DECISION_COLORS = {
    Interaction.Decision.ANSWER: 'success',
    Interaction.Decision.PARTIAL: 'info',
    Interaction.Decision.REFER: 'warning',
    Interaction.Decision.ABSTAIN: 'danger',
    Interaction.Decision.OUT_OF_SCOPE: 'danger',
}

#: Badge colour of each referral status, from waiting (orange) to done (green)
REFERRAL_STATUS_COLORS = {
    Referral.Status.OPEN: 'warning',
    Referral.Status.IN_PROGRESS: 'info',
    Referral.Status.ANSWERED: 'success',
    Referral.Status.CLOSED: 'danger',
}

#: Badge colour of each verdict on an AI answer
VERDICT_COLORS = {
    HumanLabel.Verdict.APPROVE: 'success',
    HumanLabel.Verdict.CORRECT: 'warning',
    HumanLabel.Verdict.REJECT: 'danger',
}

#: Why the verification removed a sentence (``Interaction.dropped[].reason``)
DROP_REASONS = {
    'quote': _('Quote not found in the sources'),
    'entailment': _('Quote does not support the sentence'),
}


def badge(color, text):
    """A coloured badge for detail pages: Unfold's ``label=`` columns only render in lists."""
    return format_html('<span class="musnid-badge musnid-badge-{}">{}</span>', color, text)


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


class QuestionRowDetails(TemplateSection):
    """The expanded row of the questions list: every detail the compact columns leave out."""

    template_name = 'admin/qa/question/row_details.html'

    def get_context_data(self, request, question):
        """Two lines of facts (icon, label, value, badge), what the asker sees, and the full page's address."""
        interaction = interaction_of(question)
        revision = question.latest_revision()
        try:
            referral = question.referral
        except ObjectDoesNotExist:
            referral = None
        def fact(icon, label, value, badge=None):
            return {'icon': icon, 'label': label, 'value': value, 'badge': badge}

        # Line 1: the question and the AI run; line 2: tokens, outcome and the ticket
        run = [
            fact('translate', _('language'), question.lang or '-'),
            fact('groups' if revision else 'smart_toy', _('answered by'),
                 _('Center') if revision else _('AI'), 'success' if revision else 'info'),
            fact('schedule', _('created at'), question.created_at.strftime('%Y-%m-%d %H:%M')),
        ]
        outcome = []
        if interaction:
            run += [
                fact('stairs', _('level'), interaction.get_level_display() if interaction.level else '-',
                     'warning' if interaction.level == 'D' else None),
                fact('timer', _('response time'), _('%(seconds).1f s') % {'seconds': interaction.latency_ms / 1000}),
            ]
            outcome += [
                fact('token', _('tokens'), _('%(input)s in, %(output)s out') % {
                    'input': interaction.tokens_in, 'output': interaction.tokens_out}),
                fact('error' if interaction.error else 'check_circle', _('error'),
                     _('Yes') if interaction.error else _('No'), 'danger' if interaction.error else 'success'),
            ]
        if referral:
            outcome += [
                fact('confirmation_number', _('ticket'), f'{referral.get_status_display()} · {referral.get_mode_display()}',
                     REFERRAL_STATUS_COLORS.get(referral.status)),
                fact('tag', _('follow-up number'), question.uuid),
            ]
        answer = revision.text if revision else (interaction.answer_text if interaction else '')
        return {
            'fact_rows': [row for row in (run, outcome) if row],
            'answer': Truncator(answer).chars(400),
            'change_url': reverse('admin:qa_question_change', args=[question.pk]),
        }


@admin.register(Question)
class QuestionAdmin(ModelAdmin):
    """Questions with their decision; each page shows the full AI answer and its checks."""

    # Compact columns; each row expands to the rest (QuestionRowDetails)
    list_display = ['short_text', 'asked_by', 'decision', 'center']
    list_sections = [QuestionRowDetails]
    list_filter = ['interaction__decision', 'interaction__level', 'lang', 'center']
    search_fields = ['text', 'asker__email']
    search_help_text = _('Search by question text or asker email, or paste a follow-up number.')
    list_select_related = ['center', 'interaction', 'asker', 'referral']
    date_hierarchy = 'created_at'
    # Explain the columns and sections to first-time readers, such as the competition jury
    list_before_template = 'admin/qa/question/list_help.html'
    change_form_before_template = 'admin/qa/question/change_help.html'
    fieldsets = [
        (_('Question'), {'fields': ['text', 'uuid', 'asked_by', 'lang', 'center', 'session_id', 'created_at']}),
        (_('Answer'), {'fields': ['decision', 'level', 'answer', 'kept_sentences', 'dropped_sentences', 'verdicts']}),
        (_('Retrieval'), {'fields': ['search_query', 'retrieved', 'evidence_given'], 'classes': ['collapse']}),
        (_('Run'), {
            'fields': ['model_used', 'latency', 'tokens', 'error'],
            'classes': ['collapse'],
        }),
    ]
    inlines = [AnswerRevisionInline]
    readonly_fields = [
        'text', 'uuid', 'asked_by', 'lang', 'center', 'session_id', 'created_at',
        'decision', 'level', 'answer', 'kept_sentences', 'dropped_sentences', 'verdicts',
        'search_query', 'retrieved', 'evidence_given', 'model_used', 'latency', 'tokens', 'error',
    ]

    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        """Flag revised questions, and load the revisions the expanded rows show, in two queries."""
        return super().get_queryset(request).annotate(
            revised=Exists(AnswerRevision.objects.filter(question=OuterRef('pk')))).prefetch_related('revisions')

    def get_urls(self):
        return [
            path('<path:object_id>/revise/', self.admin_site.admin_view(self.revise_view), name='qa_question_revise'),
            path('<path:object_id>/label/', self.admin_site.admin_view(self.label_view), name='qa_question_label'),
            *super().get_urls(),
        ]

    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Offer "Revise the answer" to users allowed to revise this question."""
        question = self.get_object(request, unquote(object_id))
        extra_context = extra_context or {}
        if question is not None and services.can_revise(request.user, question):
            extra_context['revise_url'] = reverse('admin:qa_question_revise', args=[question.pk])
            if interaction_of(question) is not None:
                extra_context['label_url'] = reverse('admin:qa_question_label', args=[question.pk])
        return super().change_view(request, object_id, form_url, extra_context)

    def label_view(self, request, object_id):
        """GET: the verdict form, prefilled with the reviewer's verdict or the AI answer. POST: save it."""
        question = get_object_or_404(Question.objects.select_related('interaction'), pk=unquote(object_id))
        interaction = interaction_of(question)
        if interaction is None or not services.can_revise(request.user, question):
            raise PermissionDenied
        mine = HumanLabel.objects.filter(interaction=interaction, reviewer=request.user).first()
        values = {
            'verdict': mine.verdict if mine else '',
            'reason': mine.reason if mine else '',
            'corrected_answer': (mine.corrected_answer if mine and mine.corrected_answer
                                 else self._plain_answer(question)),
        }
        error = None
        if request.method == 'POST':
            values = {key: request.POST.get(key, '') for key in values}
            try:
                services.label(interaction, request.user, values['verdict'], values['reason'],
                               values['corrected_answer'])
            except ValidationError as caught:
                error = ' '.join(caught.messages)
            else:
                self.message_user(request, _('Your verdict on the AI answer was saved.'), messages.SUCCESS)
                return HttpResponseRedirect(reverse('admin:qa_question_change', args=[question.pk]))
        return TemplateResponse(request, 'admin/qa/question/label.html', {
            **self.admin_site.each_context(request),
            'title': _('AI verdict'),
            'opts': self.model._meta,
            'original': question,
            'question': question,
            'ai_answer': interaction.answer_text,
            'values': values,
            'error': error,
            'verdicts': HumanLabel.Verdict.choices,
            'text_max': TEXT_MAX,
            'change_url': reverse('admin:qa_question_change', args=[question.pk]),
        })

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

    @display(description=_('AI verdicts'))
    def verdicts(self, question):
        """Each reviewer's verdict on the AI answer, with the reason."""
        interaction = interaction_of(question)
        labels = list(interaction.labels.select_related('reviewer')) if interaction else []
        if not labels:
            return '-'
        return format_html('<ul class="musnid-sentences musnid-compact">{}</ul>', format_html_join(
            '', '<li><span class="musnid-badge musnid-badge-{}">{}</span> {} {}</li>',
            ((VERDICT_COLORS[label.verdict], label.get_verdict_display(),
              label.reviewer.full_name if label.reviewer else '-', f'· {label.reason}' if label.reason else '')
             for label in labels),
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

    @display(description=_('evidence given to the writer'))
    def evidence_given(self, question):
        """The exact evidence text the writer received (saved since 2026-10-06), right to left."""
        interaction = interaction_of(question)
        if interaction is None or not interaction.evidence:
            return '-'
        return format_html('<pre dir="rtl" lang="ar" class="musnid-pre">{}</pre>', interaction.evidence)

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


def pending_referrals_badge(request):
    """Sidebar badge: the number of referrals waiting for an answer (empty when none)."""
    count = Referral.objects.pending().count()
    return str(count) if count else ''


@admin.register(Referral)
class ReferralAdmin(ModelAdmin):
    """
    Referred questions, as tickets: open, in progress, answered or closed.

    Read-only: status and dates change only through ``qa.services``. A specialist
    answers from the question's "Revise the answer" page, which marks the
    referral answered.
    """

    list_display = ['short_question', 'mode', 'status', 'reason', 'assigned_to', 'center', 'created_at', 'answered_at']
    list_filter = ['status', 'mode', 'reason', ('assigned_to', admin.RelatedOnlyFieldListFilter), 'center']
    # Explain statuses, modes, reasons and actions to the administrator and the jury
    list_before_template = 'admin/qa/referral/list_help.html'
    search_fields = ['question__text', 'assigned_to__email']
    list_select_related = ['question', 'center', 'assigned_to']
    date_hierarchy = 'created_at'
    actions = ['assign_to_me', 'close_selected']
    fields = ['question_link', 'mode_badge', 'reason', 'status_badge', 'assigned_to', 'center', 'created_at',
              'live_until', 'answered_at', 'closed_at', 'close_note']
    readonly_fields = fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @display(description=_('question'))
    def short_question(self, referral):
        return Truncator(referral.question.text).chars(90)

    @display(description=_('question'))
    def question_link(self, referral):
        """The referred question's page, where its answer is revised."""
        return format_html('<a href="{}" dir="auto">{}</a>',
                           reverse('admin:qa_question_change', args=[referral.question_id]), referral.question.text)

    @display(description=_('status'), ordering='status', label=REFERRAL_STATUS_COLORS)
    def status(self, referral):
        return referral.status, referral.get_status_display()

    @display(description=_('mode'), ordering='mode', label={'live': 'warning', 'ticket': 'info'})
    def mode(self, referral):
        """Live (the asker waited one minute) or a ticket answered later."""
        return referral.mode, referral.get_mode_display()

    @display(description=_('status'))
    def status_badge(self, referral):
        return badge(REFERRAL_STATUS_COLORS[referral.status], referral.get_status_display())

    @display(description=_('mode'))
    def mode_badge(self, referral):
        return badge('warning' if referral.mode == Referral.Mode.LIVE else 'info', referral.get_mode_display())

    @action(description=_('Assign selected referrals to me'))
    def assign_to_me(self, request, queryset):
        """Take each selected referral through ``assign``; refusals are counted with their reason."""
        self._apply(request, queryset, lambda referral: services.assign(referral, request.user, request.user))

    @action(description=_('Close selected referrals without an answer'))
    def close_selected(self, request, queryset):
        """Ask why on an intermediate page, then close each selected referral through ``close``."""
        if 'apply' not in request.POST:
            return TemplateResponse(request, 'admin/qa/referral/close_selected.html', {
                **self.admin_site.each_context(request),
                'title': _('Close selected referrals without an answer'),
                'opts': self.model._meta,
                'referrals': queryset.select_related('question'),
                'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
            })
        note = request.POST.get('close_note', '')
        self._apply(request, queryset, lambda referral: services.close(referral, request.user, note))
        return None

    def _apply(self, request, queryset, change):
        """Apply ``change`` to each referral; report successes and refusals with ngettext."""
        done, refused = 0, []
        for referral in queryset.select_related('question__center', 'center'):
            try:
                change(referral)
                done += 1
            except ValidationError as error:
                refused.append(f'{Truncator(referral.question.text).chars(40)}: {" ".join(error.messages)}')
        if done:
            self.message_user(request, ngettext(
                '%(count)d referral was updated.', '%(count)d referrals were updated.', done,
            ) % {'count': done}, messages.SUCCESS)
        if refused:
            self.message_user(request, ngettext(
                '%(count)d referral could not be updated: %(reasons)s',
                '%(count)d referrals could not be updated: %(reasons)s',
                len(refused),
            ) % {'count': len(refused), 'reasons': '; '.join(refused)}, messages.ERROR)


@admin.register(HumanLabel)
class HumanLabelAdmin(ModelAdmin):
    """
    Reviewers' verdicts on AI answers, for evaluation and the fine-tuning dataset.

    Read-only: verdicts are given from a question's page ("AI verdict"), through
    ``qa.services.label``.
    """

    list_display = ['short_question', 'verdict_badge', 'language', 'reviewer', 'created_at']
    list_filter = ['verdict', 'interaction__question__lang', 'interaction__decision']
    search_fields = ['interaction__question__text', 'reason', 'reviewer__email']
    list_select_related = ['interaction__question', 'reviewer']
    date_hierarchy = 'created_at'
    list_before_template = 'admin/qa/humanlabel/list_help.html'
    fields = ['question_link', 'verdict_detail', 'ai_answer', 'reason', 'corrected_answer', 'reviewer', 'created_at',
              'updated_at']
    readonly_fields = fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @display(description=_('question'))
    def short_question(self, label):
        return Truncator(label.interaction.question.text).chars(90)

    @display(description=_('question'))
    def question_link(self, label):
        """The question's page: its AI answer, evidence and checks."""
        question = label.interaction.question
        return format_html('<a href="{}" dir="auto">{}</a>', reverse('admin:qa_question_change', args=[question.pk]),
                           question.text)

    @display(description=_('verdict'), ordering='verdict', label=VERDICT_COLORS)
    def verdict_badge(self, label):
        return label.verdict, label.get_verdict_display()

    @display(description=_('verdict'))
    def verdict_detail(self, label):
        return badge(VERDICT_COLORS[label.verdict], label.get_verdict_display())

    @display(description=_('AI answer'))
    def ai_answer(self, label):
        """The AI answer the verdict is about, next to the correction."""
        return format_html('<div dir="auto" class="musnid-answer">{}</div>', label.interaction.answer_text)

    @display(description=_('language'), ordering='interaction__question__lang')
    def language(self, label):
        return label.interaction.question.lang or '-'

