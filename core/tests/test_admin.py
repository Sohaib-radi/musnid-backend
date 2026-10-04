"""Tests for ``core/admin.py`` and ``core/forms.py``: the Unfold admin."""

from django.contrib import admin
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import StackedInline, TabularInline

from core.models import Center, Membership, User
from core.tests.support import make_center, make_membership, make_user

ADMIN = Membership.Role.CENTER_ADMIN
SPECIALIST = Membership.Role.SPECIALIST

# Management form of the read-only memberships inline on the user page.
INLINE_MANAGEMENT = {'memberships-TOTAL_FORMS': '0', 'memberships-INITIAL_FORMS': '0'}


class UnfoldEverywhereTests(TestCase):
    """Every registered admin and inline uses Unfold's classes."""

    def test_every_model_admin_uses_unfold(self):
        for model, model_admin in admin.site._registry.items():
            with self.subTest(model=model.__name__):
                self.assertIsInstance(model_admin, UnfoldModelAdmin)

    def test_every_inline_uses_unfold(self):
        for model, model_admin in admin.site._registry.items():
            for inline in model_admin.inlines:
                with self.subTest(model=model.__name__, inline=inline.__name__):
                    self.assertTrue(issubclass(inline, (TabularInline, StackedInline)))

    def test_expected_models_are_registered(self):
        self.assertEqual(set(admin.site._registry), {User, Center, Membership, Group})


class AdminTestCase(TestCase):
    """Logs in a superuser; helpers for admin URLs and messages."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = make_user(is_staff=True, is_superuser=True)

    def setUp(self):
        self.client.force_login(self.superuser)

    def url(self, model, view, *args):
        return reverse(f'admin:core_{model._meta.model_name}_{view}', args=args)

    def messages(self, response):
        return [str(message) for message in response.context['messages']]


class PagesTests(AdminTestCase):
    """Changelist, add and change pages of every admin respond."""

    def test_pages_respond(self):
        center = make_center()
        membership = make_membership(center=center)
        urls = [
            self.url(User, 'changelist'), self.url(User, 'add'), self.url(User, 'change', membership.user.pk),
            self.url(Center, 'changelist'), self.url(Center, 'add'), self.url(Center, 'change', center.pk),
            self.url(Membership, 'changelist'), self.url(Membership, 'add'),
            self.url(Membership, 'change', membership.pk),
            reverse('admin:auth_group_changelist'), reverse('admin:auth_group_add'),
            # Django's UserAdmin names this URL auth_user_* even for a custom user model.
            reverse('admin:auth_user_password_change', args=[membership.user.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_search(self):
        make_user(email='amina@example.com')
        response = self.client.get(self.url(User, 'changelist'), {'q': 'AMINA'})
        self.assertContains(response, 'amina@example.com')


class UserAdminTests(AdminTestCase):
    """Creating and editing email-identified users."""

    def test_add_user_with_password(self):
        response = self.client.post(self.url(User, 'add'), {
            'email': 'amina@example.com', 'full_name': 'Amina',
            'usable_password': 'true', 'password1': 'a-Long-pass-123', 'password2': 'a-Long-pass-123',
            **INLINE_MANAGEMENT,
        })
        user = User.objects.get(email='amina@example.com')
        self.assertRedirects(response, self.url(User, 'change', user.pk))
        self.assertTrue(user.check_password('a-Long-pass-123'))

    def test_add_user_with_existing_email_in_other_case(self):
        make_user(email='amina@example.com')
        response = self.client.post(self.url(User, 'add'), {
            'email': 'AMINA@example.com', 'full_name': 'Other',
            'usable_password': 'false', **INLINE_MANAGEMENT,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'A user with this email address already exists.')

    def test_change_page_shows_memberships_read_only(self):
        membership = make_membership(center=make_center(name='Dar al-Ifta'))
        response = self.client.get(self.url(User, 'change', membership.user.pk))
        self.assertContains(response, 'Dar al-Ifta')
        self.assertNotContains(response, 'name="memberships-0-role"')


class CenterAdminTests(AdminTestCase):
    """Center form, inline and the default-center action."""

    def center_data(self, **overrides):
        data = {
            'name': 'Dar al-Ifta', 'slug': 'dar-al-ifta', 'country': 'MA', 'description': '',
            'contact_email': '', 'website': '', 'telegram_chat_id': '', 'languages': ['ar', 'fr'],
            'is_active': 'on',
            'core_membership_set-TOTAL_FORMS': '0', 'core_membership_set-INITIAL_FORMS': '0',
        }
        data.update(overrides)
        return data

    def test_languages_are_checkboxes_and_saved(self):
        response = self.client.get(self.url(Center, 'add'))
        self.assertContains(response, 'type="checkbox" name="languages" value="ar"')
        self.client.post(self.url(Center, 'add'), self.center_data())
        self.assertEqual(Center.objects.get(slug='dar-al-ifta').languages, ['ar', 'fr'])

    def test_second_default_is_a_form_error(self):
        make_center(is_default=True)
        response = self.client.post(self.url(Center, 'add'), self.center_data(is_default='on'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Only one center can be the default center.')
        self.assertFalse(Center.objects.filter(slug='dar-al-ifta').exists())

    def test_slug_is_prepopulated_from_name(self):
        self.assertEqual(admin.site._registry[Center].prepopulated_fields, {'slug': ['name']})

    def run_make_default(self, centers):
        return self.client.post(self.url(Center, 'changelist'), {
            'action': 'make_default', '_selected_action': [center.pk for center in centers],
        }, follow=True)

    def test_make_default_action(self):
        old, new = make_center(is_default=True), make_center()
        response = self.run_make_default([new])
        self.assertEqual(self.messages(response), [f'“{new.name}” is now the default center.'])
        old.refresh_from_db()
        new.refresh_from_db()
        self.assertTrue(new.is_default)
        self.assertFalse(old.is_default)

    def test_make_default_requires_exactly_one_center(self):
        first, second = make_center(), make_center()
        response = self.run_make_default([first, second])
        self.assertEqual(self.messages(response), ['Select exactly one center to make it the default.'])
        self.assertFalse(Center.objects.filter(is_default=True).exists())

    def test_change_page_lists_memberships_read_only(self):
        membership = make_membership()
        response = self.client.get(self.url(Center, 'change', membership.center.pk))
        self.assertContains(response, membership.user.email)
        self.assertNotContains(response, 'name="core_membership_set-0-role"')


class MembershipAdminTests(AdminTestCase):
    """Memberships change only through the services and are never deleted."""

    def test_add_goes_through_the_service(self):
        user, center = make_user(), make_center()
        self.client.post(self.url(Membership, 'add'), {'user': user.pk, 'center': center.pk, 'role': ADMIN})
        membership = Membership.objects.get(user=user, center=center)
        self.assertEqual(membership.role, ADMIN)
        self.assertTrue(membership.is_active)

    def test_add_reports_service_rules_as_form_errors(self):
        center = make_center()
        inactive = make_user(is_active=False)
        member = make_membership(center=center).user
        for user, message in (
            (inactive, 'This user account is deactivated.'),
            (member, 'This user is already an active member of this center.'),
        ):
            with self.subTest(message=message):
                response = self.client.post(
                    self.url(Membership, 'add'), {'user': user.pk, 'center': center.pk, 'role': SPECIALIST},
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, message)

    def test_change_role(self):
        membership = make_membership()
        self.client.post(self.url(Membership, 'change', membership.pk), {'role': ADMIN})
        membership.refresh_from_db()
        self.assertEqual(membership.role, ADMIN)

    def test_demoting_the_last_admin_is_a_form_error(self):
        membership = make_membership(role=ADMIN)
        response = self.client.post(self.url(Membership, 'change', membership.pk), {'role': SPECIALIST})
        self.assertContains(response, 'A center must keep at least one active center admin.')
        membership.refresh_from_db()
        self.assertEqual(membership.role, ADMIN)

    def test_only_role_is_editable_on_change(self):
        membership = make_membership()
        response = self.client.get(self.url(Membership, 'change', membership.pk))
        self.assertContains(response, 'name="role"')
        self.assertNotContains(response, 'name="user"')
        self.assertNotContains(response, 'name="center"')

    def test_autocomplete_for_user_and_center(self):
        self.assertEqual(admin.site._registry[Membership].autocomplete_fields, ['user', 'center'])

    def run_offboard(self, selected):
        return self.client.post(self.url(Membership, 'changelist'), {
            'action': 'offboard', '_selected_action': [membership.pk for membership in selected],
        }, follow=True)

    def test_offboard_action(self):
        center = make_center()
        make_membership(center=center, role=ADMIN)
        first, second = make_membership(center=center), make_membership(center=center)
        response = self.run_offboard([first, second])
        self.assertEqual(self.messages(response), ['2 memberships were offboarded.'])
        for membership in (first, second):
            membership.refresh_from_db()
            self.assertFalse(membership.is_active)
            self.assertIsNotNone(membership.left_at)

    def test_offboard_action_reports_refusals(self):
        last_admin = make_membership(role=ADMIN)
        response = self.run_offboard([last_admin])
        self.assertEqual(self.messages(response), [
            f'1 membership could not be offboarded: {last_admin}: '
            'A center must keep at least one active center admin.',
        ])
        last_admin.refresh_from_db()
        self.assertTrue(last_admin.is_active)

    def test_offboard_message_singular(self):
        response = self.run_offboard([make_membership()])
        self.assertEqual(self.messages(response), ['1 membership was offboarded.'])

    def test_memberships_cannot_be_deleted(self):
        membership = make_membership()
        response = self.client.get(self.url(Membership, 'changelist'))
        self.assertNotIn('delete_selected', response.context['action_form'].fields['action'].choices.__repr__())
        self.assertEqual(self.client.get(self.url(Membership, 'delete', membership.pk)).status_code, 403)
