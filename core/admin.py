"""
Admin for the core models, styled with Unfold (ADR 0008).

Every admin inherits ``unfold.admin.ModelAdmin`` and every inline uses Unfold's
inline classes; ``core/tests/test_admin.py`` fails otherwise. ``Group`` is
re-registered for the same reason.

Memberships change only through ``core.services.memberships`` (ADR 0007):

* ``MembershipAdmin`` creates with ``add_member`` and changes the role with
  ``change_role``; its form runs the same checks first, so rule violations
  appear as form errors. Ending a membership is the "Offboard" action, and
  deletion is disabled.
* The membership inlines on users and centers are read-only, with a link to
  the membership's own page.

Center review (ADR 0013) goes through ``core.services.centers``: bulk actions,
and Approve/Reject buttons that open confirmation dialogs, shown only on
pending centers and only to users with the change permission.
"""

from django.contrib import admin, messages
from django.contrib.admin.utils import unquote
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponseNotAllowed, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.utils.decorators import method_decorator
from django.utils.translation import ngettext
from django.views.decorators.debug import sensitive_post_parameters
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action, display

from core.forms import (
    AdminPasswordChangeForm, ApiCredentialAddForm, CenterAdminForm, MembershipAdminForm, UserChangeForm, UserCreationForm,
)
from core.models import AISettings, ApiCredential, Center, Membership, User
from core.services import centers, credentials, memberships

admin.site.unregister(Group)


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    """Django's group admin with Unfold's styling."""


class ReadOnlyMembershipInline(TabularInline):
    """
    Memberships shown on another object's page, read-only.

    Editing here would bypass the membership services, so the inline only
    lists memberships and links to each one.
    """

    model = Membership
    extra = 0
    can_delete = False
    show_change_link = True
    ordering = ['-is_active', '-created_at']

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class UserMembershipInline(ReadOnlyMembershipInline):
    """A user's memberships, one row per center."""

    fk_name = 'user'
    fields = ['center', 'role', 'is_active', 'left_at']
    readonly_fields = fields


class CenterMembershipInline(ReadOnlyMembershipInline):
    """A center's memberships, one row per user."""

    fk_name = 'center'
    fields = ['user', 'role', 'is_active', 'left_at']
    readonly_fields = fields


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    """Users, identified by email."""

    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm

    list_display = ['email', 'full_name', 'preferred_lang', 'is_active', 'is_staff', 'is_verified', 'created_at']
    list_filter = ['is_active', 'is_staff', 'is_superuser', 'is_verified', 'preferred_lang', 'groups']
    search_fields = ['email', 'full_name']
    ordering = ['-created_at']
    readonly_fields = ['uuid', 'last_login', 'created_at', 'updated_at']
    filter_horizontal = ['groups', 'user_permissions']
    inlines = [UserMembershipInline]

    fieldsets = [
        (_('Profile'), {
            'fields': ['email', 'full_name', 'preferred_lang', 'avatar', 'telegram_chat_id', 'uuid', 'password'],
        }),
        (_('Status'), {'fields': ['is_active', 'is_verified']}),
        (_('Permissions'), {
            'fields': ['is_staff', 'is_superuser', 'groups', 'user_permissions'],
            'classes': ['collapse'],
        }),
        (_('Dates'), {'fields': ['last_login', 'created_at', 'updated_at']}),
    ]
    add_fieldsets = [
        (None, {
            'classes': ['wide'],
            'fields': ['email', 'full_name', 'usable_password', 'password1', 'password2'],
        }),
    ]


def pending_centers_badge(request):
    """Sidebar badge: the number of centers waiting for review (empty when none)."""
    count = Center.objects.pending().count()
    return str(count) if count else ''


@admin.register(Center)
class CenterAdmin(ModelAdmin):
    """Centers of specialists: review, default center, settings."""

    form = CenterAdminForm
    change_form_template = 'admin/core/center/change_form.html'
    list_filter = ['status', 'is_active', 'is_default', 'country']
    search_fields = ['name', 'slug', 'contact_email']
    prepopulated_fields = {'slug': ['name']}
    readonly_fields = ['status', 'reviewed_at', 'reviewed_by', 'created_at', 'updated_at']
    inlines = [CenterMembershipInline]
    actions = ['approve_selected', 'reject_selected', 'make_default']
    list_before_template = 'admin/core/center/list_help.html'

    fieldsets = [
        (None, {'fields': ['name', 'slug', 'country', 'logo', 'description']}),
        (_('Contact'), {'fields': ['contact_email', 'website', 'telegram_chat_id']}),
        (_('Service'), {'fields': ['languages', 'is_active', 'is_default']}),
        (_('Review'), {'fields': ['status', 'rejection_reason', 'reviewed_at', 'reviewed_by']}),
        (_('Dates'), {'fields': ['created_at', 'updated_at']}),
    ]

    def get_list_display(self, request):
        columns = ['name', 'country', 'review_status', 'is_active', 'is_default', 'created_at']
        if self.has_change_permission(request):
            columns.append(self._review_column(request))
        return columns

    def get_readonly_fields(self, request, obj=None):
        # The reason is part of the review: written by reject(), never edited afterwards.
        return [*super().get_readonly_fields(request, obj), 'rejection_reason']

    @display(
        description=_('Review status'),
        label={
            Center.Status.PENDING: 'warning',
            Center.Status.APPROVED: 'success',
            Center.Status.REJECTED: 'danger',
        },
    )
    def review_status(self, center):
        """Coloured badge: amber pending, green approved, red rejected."""
        return center.status, center.get_status_display()

    def _review_column(self, request):
        """
        Build the "Review" column for this request.

        A closure over ``request`` (needed for the CSRF token in the dialogs)
        keeps the admin instance free of per-request state.
        """
        def review(center):
            if center.status != Center.Status.PENDING:
                return ''
            return self.review_buttons(request, center)
        review.short_description = _('Review')
        return review

    def review_buttons(self, request, center):
        """Approve and Reject buttons with their confirmation dialogs."""
        return render_to_string('admin/core/center/review_buttons.html', {
            'center': center,
            'approve_url': reverse('admin:core_center_approve', args=[center.pk]),
            'reject_url': reverse('admin:core_center_reject', args=[center.pk]),
            'next': request.get_full_path(),
        }, request=request)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        center = self.get_object(request, unquote(object_id))
        extra_context = extra_context or {}
        if center and center.status == Center.Status.PENDING and self.has_change_permission(request, center):
            extra_context['review_buttons'] = self.review_buttons(request, center)
        return super().change_view(request, object_id, form_url, extra_context)

    def get_urls(self):
        review_urls = [
            path('<path:object_id>/approve/', self.admin_site.admin_view(self.approve_view),
                 name='core_center_approve'),
            path('<path:object_id>/reject/', self.admin_site.admin_view(self.reject_view),
                 name='core_center_reject'),
        ]
        return review_urls + super().get_urls()

    def approve_view(self, request, object_id):
        """POST: approve one pending center (from a row or the change page)."""
        return self._review_view(request, object_id, lambda center: centers.approve(center, request.user),
                                 _('“%(center)s” was approved.'))

    def reject_view(self, request, object_id):
        """POST: reject one pending center with the reason typed in its dialog (field named per center)."""
        # Per-center name: in the list every row's dialog is posted with the changelist form
        reason = request.POST.get(f'rejection_reason_{unquote(object_id)}') or request.POST.get('rejection_reason', '')
        return self._review_view(request, object_id, lambda center: centers.reject(center, request.user, reason),
                                 _('“%(center)s” was rejected.'))

    def _review_view(self, request, object_id, review, success_message):
        if request.method != 'POST':
            return HttpResponseNotAllowed(['POST'])
        center = get_object_or_404(Center, pk=unquote(object_id))
        if not self.has_change_permission(request, center):
            raise PermissionDenied
        try:
            review(center)
            self.message_user(request, success_message % {'center': center}, messages.SUCCESS)
        except ValidationError as error:
            self.message_user(request, ' '.join(error.messages), messages.ERROR)
        target = request.POST.get('next', '')
        if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
            target = reverse('admin:core_center_changelist')
        return HttpResponseRedirect(target)

    @action(description=_('Approve selected centers'), permissions=['change'])
    def approve_selected(self, request, queryset):
        """Approve every selected pending center; others are skipped and counted."""
        self._bulk_review(request, queryset, lambda center: centers.approve(center, request.user))

    @action(description=_('Reject selected centers'), permissions=['change'])
    def reject_selected(self, request, queryset):
        """Ask for a reason on an intermediate page, then reject every selected pending center."""
        if 'apply' not in request.POST:
            return TemplateResponse(request, 'admin/core/center/reject_selected.html', {
                **self.admin_site.each_context(request),
                'title': _('Reject selected centers'),
                'opts': self.model._meta,
                'centers': queryset,
                'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
            })
        reason = request.POST.get('rejection_reason', '')
        self._bulk_review(request, queryset, lambda center: centers.reject(center, request.user, reason))
        return None

    def _bulk_review(self, request, queryset, review):
        """Apply ``review`` to each center; report successes and refusals with ngettext."""
        done, refused = [], []
        for center in queryset:
            try:
                review(center)
                done.append(center)
            except ValidationError as error:
                refused.append(f'{center}: {" ".join(error.messages)}')
        if done:
            self.message_user(request, ngettext(
                '%(count)d center was reviewed.', '%(count)d centers were reviewed.', len(done),
            ) % {'count': len(done)}, messages.SUCCESS)
        if refused:
            self.message_user(request, ngettext(
                '%(count)d center could not be reviewed: %(reasons)s',
                '%(count)d centers could not be reviewed: %(reasons)s',
                len(refused),
            ) % {'count': len(refused), 'reasons': '; '.join(refused)}, messages.ERROR)

    @action(description=_('Make selected center the default'))
    def make_default(self, request, queryset):
        """Make the one selected center the default, through ``Center.make_default()``."""
        if queryset.count() != 1:
            self.message_user(
                request, _('Select exactly one center to make it the default.'), messages.ERROR,
            )
            return
        center = queryset.get()
        try:
            center.make_default()
        except ValidationError as error:
            self.message_user(request, ' '.join(error.messages), messages.ERROR)
            return
        self.message_user(
            request,
            _('“%(center)s” is now the default center.') % {'center': center},
            messages.SUCCESS,
        )


@admin.register(Membership)
class MembershipAdmin(ModelAdmin):
    """Memberships: created and changed through the services, never deleted."""

    form = MembershipAdminForm
    list_display = ['user', 'center', 'role', 'is_active', 'created_at', 'left_at']
    list_before_template = 'admin/core/membership/list_help.html'
    list_filter = ['role', 'is_active', 'center']
    search_fields = ['user__email', 'user__full_name', 'center__name']
    autocomplete_fields = ['user', 'center']
    list_select_related = ['user', 'center']
    actions = ['offboard']

    def get_fields(self, request, obj=None):
        if obj is None:
            return ['user', 'center', 'role']
        return ['uuid', 'user', 'center', 'role', 'is_active', 'left_at', 'created_at', 'updated_at']

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return []
        return ['uuid', 'user', 'center', 'is_active', 'left_at', 'created_at', 'updated_at']

    def get_actions(self, request):
        # Memberships are ended with "Offboard", never deleted.
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        """Save through the services; the form has already run their checks."""
        if change:
            memberships.change_role(obj, form.cleaned_data['role'])
        else:
            created = memberships.add_member(obj.center, obj.user.email, obj.role)
            obj.pk = created.pk
            obj._state.adding = False
        obj.refresh_from_db()

    @action(description=_('Offboard selected memberships'))
    def offboard(self, request, queryset):
        """End each selected membership through ``offboard()``, reporting refusals."""
        done, refused = 0, []
        for membership in queryset.select_related('user', 'center'):
            try:
                memberships.offboard(membership)
                done += 1
            except ValidationError as error:
                refused.append(f'{membership}: {" ".join(error.messages)}')
        if done:
            self.message_user(
                request,
                ngettext(
                    '%(count)d membership was offboarded.',
                    '%(count)d memberships were offboarded.',
                    done,
                ) % {'count': done},
                messages.SUCCESS,
            )
        if refused:
            self.message_user(
                request,
                ngettext(
                    '%(count)d membership could not be offboarded: %(reasons)s',
                    '%(count)d memberships could not be offboarded: %(reasons)s',
                    len(refused),
                ) % {'count': len(refused), 'reasons': '; '.join(refused)},
                messages.ERROR,
            )


@admin.register(ApiCredential)
class ApiCredentialAdmin(ModelAdmin):
    """
    Provider API keys (ADR 0014): added once, then only viewed, revoked or deleted.

    The secret is entered on the add page only and never displayed: pages show
    the masked form. Keys cannot be edited (no change permission); a new key is
    added instead, which revokes the previous one.
    """

    add_form = ApiCredentialAddForm
    list_display = ['name', 'provider', 'masked', 'is_active', 'created_at', 'revoked_at']
    list_before_template = 'admin/core/apicredential/list_help.html'
    list_filter = ['provider', 'is_active']
    search_fields = ['name']
    actions = ['revoke_selected']
    view_fields = ['provider', 'name', 'masked', 'is_active', 'created_by', 'created_at', 'revoked_at', 'revoked_by']

    @display(description=_('API key'))
    def masked(self, credential):
        """Only the masked form (e.g. sk-...abcd) is ever shown."""
        return credential.masked

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs['form'] = self.add_form
        return super().get_form(request, obj, **kwargs)

    def get_fields(self, request, obj=None):
        return ['provider', 'name', 'secret'] if obj is None else self.view_fields

    def get_readonly_fields(self, request, obj=None):
        return [] if obj is None else self.view_fields

    def has_change_permission(self, request, obj=None):
        return False

    def has_revoke_permission(self, request, obj=None):
        """Revoking needs the delete permission: it is the softer way of removing a key."""
        return self.has_delete_permission(request, obj)

    @method_decorator(sensitive_post_parameters('secret'))
    def add_view(self, request, form_url='', extra_context=None):
        return super().add_view(request, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        """Create through the service, which encrypts and revokes the previous key."""
        created = credentials.add_credential(
            form.cleaned_data['provider'], form.cleaned_data['name'], form.cleaned_data['secret'],
            created_by=request.user,
        )
        obj.pk = created.pk
        obj._state.adding = False
        obj.refresh_from_db()

    @action(description=_('Revoke selected API keys'), permissions=['revoke'])
    def revoke_selected(self, request, queryset):
        """Revoke every selected key; already revoked keys are left as they are."""
        count = 0
        for credential in queryset:
            if credential.is_active:
                credentials.revoke(credential, request.user)
                count += 1
        self.message_user(request, ngettext(
            '%(count)d API key was revoked.', '%(count)d API keys were revoked.', count,
        ) % {'count': count}, messages.SUCCESS)


@admin.register(AISettings)
class AISettingsAdmin(ModelAdmin):
    """The single AI settings row: chat model and temperature of the crews."""

    list_display = ['chat_model', 'temperature', 'updated_at']
    fields = ['chat_model', 'verifier_model', 'temperature']

    def has_add_permission(self, request):
        return not AISettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
