"""
Read-only admin of the messages the bot sent (ADR 0022), with a "Send again"
action for failed ones, through ``telegram_bot.services.resend``.
"""

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.html import format_html
from django.utils.text import Truncator
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext
from unfold.admin import ModelAdmin
from unfold.decorators import action, display

from telegram_bot import services
from telegram_bot.models import TelegramMessage


@admin.register(TelegramMessage)
class TelegramMessageAdmin(ModelAdmin):
    """Every attempt to send a message: what, where, and Telegram's error when it failed."""

    list_display = ['created_at', 'kind', 'status', 'chat_id', 'question', 'short_error']
    list_filter = ['status', 'kind']
    search_fields = ['referral__question__text', 'error']
    list_select_related = ['referral__question']
    date_hierarchy = 'created_at'
    actions = ['send_again']
    fields = ['created_at', 'kind', 'status', 'chat_id', 'message_id', 'referral_link', 'text', 'error']
    readonly_fields = fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @display(description=_('status'), ordering='status', label={'sent': 'success', 'failed': 'danger'})
    def status(self, message):
        return message.status, message.get_status_display()

    @display(description=_('question'))
    def question(self, message):
        return Truncator(message.referral.question.text).chars(60)

    @display(description=_('error'))
    def short_error(self, message):
        return Truncator(message.error).chars(60) or '-'

    @display(description=_('referral'))
    def referral_link(self, message):
        """The referral's page in the admin."""
        return format_html('<a href="{}" dir="auto">{}</a>',
                           reverse('admin:qa_referral_change', args=[message.referral_id]),
                           message.referral.question.text)

    @action(description=_('Send selected failed messages again'))
    def send_again(self, request, queryset):
        """Resend each selected failed message; report successes and refusals with ngettext."""
        sent, refused = 0, []
        for message in queryset.select_related('referral__center', 'referral__question'):
            try:
                attempt = services.resend(message)
            except ValidationError as error:
                refused.append(' '.join(error.messages))
                continue
            if attempt.status == TelegramMessage.Status.SENT:
                sent += 1
            else:
                refused.append(attempt.error)
        if sent:
            self.message_user(request, ngettext(
                '%(count)d message was sent.', '%(count)d messages were sent.', sent,
            ) % {'count': sent}, messages.SUCCESS)
        if refused:
            self.message_user(request, ngettext(
                '%(count)d message could not be sent: %(reasons)s',
                '%(count)d messages could not be sent: %(reasons)s',
                len(refused),
            ) % {'count': len(refused), 'reasons': '; '.join(refused)}, messages.ERROR)
