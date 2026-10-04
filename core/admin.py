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
"""

from django.contrib import admin, messages
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action

from core.forms import (
    AdminPasswordChangeForm, CenterAdminForm, MembershipAdminForm, UserChangeForm, UserCreationForm,
)
from core.models import Center, Membership, User
from core.services import memberships

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


@admin.register(Center)
class CenterAdmin(ModelAdmin):
    """Centers of specialists, with the default-center action."""

    form = CenterAdminForm
    list_display = ['name', 'country', 'is_active', 'is_default', 'created_at']
    list_filter = ['is_active', 'is_default', 'country']
    search_fields = ['name', 'slug', 'contact_email']
    prepopulated_fields = {'slug': ['name']}
    readonly_fields = ['created_at', 'updated_at']
    inlines = [CenterMembershipInline]
    actions = ['make_default']

    fieldsets = [
        (None, {'fields': ['name', 'slug', 'country', 'logo', 'description']}),
        (_('Contact'), {'fields': ['contact_email', 'website', 'telegram_chat_id']}),
        (_('Service'), {'fields': ['languages', 'is_active', 'is_default']}),
        (_('Dates'), {'fields': ['created_at', 'updated_at']}),
    ]

    @action(description=_('Make selected center the default'))
    def make_default(self, request, queryset):
        """Make the one selected center the default, through ``Center.make_default()``."""
        if queryset.count() != 1:
            self.message_user(
                request, _('Select exactly one center to make it the default.'), messages.ERROR,
            )
            return
        center = queryset.get()
        center.make_default()
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
