"""Tests for ``core/admin.py`` and ``core/forms.py``: the Unfold admin."""

import re

from django.contrib import admin
from django.contrib.auth.models import Group, Permission
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import StackedInline, TabularInline

from core.admin import pending_centers_badge
from knowledge.models import SourceChunk, SourceDocument
from qa.models import Question, Referral
from telegram_bot.models import TelegramMessage
from core.models import AISettings, ApiCredential, Center, Membership, User
from core.tests.support import (
    TEST_ENCRYPTION_KEYS, make_center, make_credential, make_membership, make_openai_key, make_user,
)

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
        self.assertEqual(
            set(admin.site._registry),
            {User, Center, Membership, Group, OutstandingToken, BlacklistedToken, ApiCredential,
             SourceDocument, SourceChunk, AISettings, Question, Referral, TelegramMessage},
        )


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


class CenterReviewAdminTests(AdminTestCase):
    """Review badge, Review column, dialogs, review URLs, bulk actions, sidebar badge."""

    def setUp(self):
        super().setUp()
        self.pending = make_center(name='Pending Center', status=Center.Status.PENDING)
        self.approved = make_center(name='Approved Center')

    def review_url(self, center, kind):
        return reverse(f'admin:core_center_{kind}', args=[center.pk])

    def test_badge_shows_the_translated_status(self):
        response = self.client.get(self.url(Center, 'changelist'))
        self.assertContains(response, 'Pending review')
        self.assertContains(response, 'Approved')

    def test_buttons_and_dialogs_on_pending_rows_only(self):
        response = self.client.get(self.url(Center, 'changelist'))
        self.assertContains(response, f'id="approve-{self.pending.pk}"')
        self.assertContains(response, f'id="reject-{self.pending.pk}"')
        self.assertNotContains(response, f'id="approve-{self.approved.pk}"')
        self.assertContains(response, 'name="rejection_reason" rows="4" required')

    def test_buttons_on_the_pending_change_page_only(self):
        self.assertContains(self.client.get(self.url(Center, 'change', self.pending.pk)),
                            f'action="{self.review_url(self.pending, "approve")}"')
        self.assertNotContains(self.client.get(self.url(Center, 'change', self.approved.pk)),
                               f'id="approve-{self.approved.pk}"')

    def test_approve(self):
        response = self.client.post(self.review_url(self.pending, 'approve'), {'next': '/admin/core/center/'}, follow=True)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, Center.Status.APPROVED)
        self.assertEqual(self.pending.reviewed_by, self.superuser)
        self.assertEqual(self.messages(response), ['“Pending Center” was approved.'])

    def test_reject_requires_a_reason(self):
        response = self.client.post(self.review_url(self.pending, 'reject'), {'rejection_reason': ' '}, follow=True)
        self.assertEqual(self.messages(response), ['A reason is required to reject a center.'])
        self.client.post(self.review_url(self.pending, 'reject'), {'rejection_reason': 'Incomplete.'})
        self.pending.refresh_from_db()
        self.assertEqual((self.pending.status, self.pending.rejection_reason), (Center.Status.REJECTED, 'Incomplete.'))

    def test_reviewing_a_non_pending_center_is_refused(self):
        response = self.client.post(self.review_url(self.approved, 'approve'), follow=True)
        self.assertEqual(self.messages(response), ['Only a pending center can be reviewed.'])

    def test_review_urls_are_post_only(self):
        self.assertEqual(self.client.get(self.review_url(self.pending, 'approve')).status_code, 405)

    def test_unsafe_next_falls_back_to_the_changelist(self):
        response = self.client.post(self.review_url(self.pending, 'approve'), {'next': 'https://evil.example/'})
        self.assertRedirects(response, self.url(Center, 'changelist'), fetch_redirect_response=False)

    def test_staff_who_are_not_superusers_cannot_enter(self):
        viewer = make_user(is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_center'))
        self.client.force_login(viewer)
        response = self.client.get(self.url(Center, 'changelist'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('admin:login'), response['Location'])
        self.assertEqual(self.client.post(self.review_url(self.pending, 'approve')).status_code, 302)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, Center.Status.PENDING)

    def run_action(self, action, centers, **extra):
        return self.client.post(self.url(Center, 'changelist'), {
            'action': action, '_selected_action': [center.pk for center in centers], **extra,
        }, follow=True)

    def test_bulk_approve(self):
        response = self.run_action('approve_selected', [self.pending, self.approved])
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, Center.Status.APPROVED)
        self.assertEqual(self.messages(response), [
            '1 center was reviewed.',
            '1 center could not be reviewed: Approved Center: Only a pending center can be reviewed.',
        ])

    def test_bulk_reject_asks_for_a_reason_first(self):
        response = self.run_action('reject_selected', [self.pending])
        self.assertContains(response, 'name="rejection_reason" rows="4" required')
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, Center.Status.PENDING)
        self.run_action('reject_selected', [self.pending], apply='1', rejection_reason='Incomplete.')
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, Center.Status.REJECTED)

    def test_make_default_refuses_a_pending_center(self):
        response = self.run_action('make_default', [self.pending])
        self.assertEqual(self.messages(response), ['Only an approved center can be the default center.'])

    def test_sidebar_badge_counts_pending_centers(self):
        self.assertEqual(pending_centers_badge(None), '1')
        Center.objects.update(status=Center.Status.APPROVED)
        self.assertEqual(pending_centers_badge(None), '')


@override_settings(FIELD_ENCRYPTION_KEYS=TEST_ENCRYPTION_KEYS)
class ApiCredentialAdminTests(AdminTestCase):
    """The secret is never shown; keys are added, viewed, revoked or deleted, never edited."""

    def setUp(self):
        super().setUp()
        self.secret = make_openai_key()

    def add(self, secret, name='Production'):
        return self.client.post(self.url(ApiCredential, 'add'), {
            'provider': 'openai', 'name': name, 'secret': secret,
        })

    def input_tag(self, html, name):
        return re.search(rf'<input[^>]*name="{name}"[^>]*>', html).group(0)

    def test_add_page_has_no_autofill_and_no_value(self):
        html = self.client.get(self.url(ApiCredential, 'add')).content.decode()
        secret_input = self.input_tag(html, 'secret')
        for attribute in ('type="password"', 'autocomplete="new-password"', 'data-1p-ignore', 'data-lpignore="true"'):
            self.assertIn(attribute, secret_input)
        self.assertNotIn('value=', secret_input)
        name_input = self.input_tag(html, 'name')
        for attribute in ('autocomplete="off"', 'data-1p-ignore', 'data-lpignore="true"'):
            self.assertIn(attribute, name_input)

    def test_add_goes_through_the_service(self):
        response = self.add(self.secret)
        credential = ApiCredential.objects.get()
        self.assertRedirects(response, self.url(ApiCredential, 'changelist'), fetch_redirect_response=False)
        self.assertEqual(credential.created_by, self.superuser)
        self.assertEqual(credential.masked, f'sk-...{self.secret[-4:]}')

    def test_invalid_submission_does_not_echo_the_secret(self):
        response = self.add('sk-bad key with spaces 123')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This does not look like an OpenAI API key')
        self.assertNotContains(response, 'sk-bad key with spaces 123')
        self.assertFalse(ApiCredential.objects.exists())

    def test_duplicate_is_refused(self):
        make_credential(secret=self.secret)
        self.assertContains(self.add(self.secret), 'This API key was already added.')

    def test_list_and_detail_show_only_the_masked_key(self):
        credential = make_credential(secret=self.secret)
        for url in (self.url(ApiCredential, 'changelist'), self.url(ApiCredential, 'change', credential.pk)):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, credential.masked)
                self.assertNotContains(response, self.secret)
                self.assertNotContains(response, credential.encrypted_secret)
                self.assertNotContains(response, credential.fingerprint)

    def test_detail_is_read_only_and_edit_is_403(self):
        credential = make_credential(secret=self.secret)
        url = self.url(ApiCredential, 'change', credential.pk)
        self.assertNotContains(self.client.get(url), 'name="name"')
        self.assertEqual(self.client.post(url, {'provider': 'openai', 'name': 'Changed'}).status_code, 403)
        credential.refresh_from_db()
        self.assertEqual(credential.name, 'Test key')

    def test_revoke_action(self):
        credential = make_credential(secret=self.secret)
        response = self.client.post(self.url(ApiCredential, 'changelist'), {
            'action': 'revoke_selected', '_selected_action': [credential.pk],
        }, follow=True)
        self.assertEqual(self.messages(response), ['1 API key was revoked.'])
        credential.refresh_from_db()
        self.assertFalse(credential.is_active)
        self.assertEqual(credential.revoked_by, self.superuser)

    def test_delete_is_allowed(self):
        credential = make_credential(secret=self.secret)
        self.client.post(self.url(ApiCredential, 'delete', credential.pk), {'post': 'yes'})
        self.assertFalse(ApiCredential.objects.exists())

    def test_add_view_hides_the_secret_from_error_reports(self):
        request = RequestFactory().post('/', {'provider': 'openai', 'name': 'x', 'secret': 'sk-bad'})
        request.user = self.superuser
        request._dont_enforce_csrf_checks = True
        admin.site._registry[ApiCredential].add_view(request)
        self.assertEqual(request.sensitive_post_parameters, ('secret',))


class SuperuserOnlyAdminTests(TestCase):
    """The admin is for platform administrators only (core/sites.py)."""

    def login(self, user):
        return self.client.post(reverse('admin:login'), {'username': user.email, 'password': 'secret-pass-123',
                                                         'next': reverse('admin:index')})

    def test_the_site_is_the_superuser_site(self):
        self.assertEqual(type(admin.site).__name__, 'SuperuserAdminSite')

    def test_superuser_signs_in(self):
        superuser = make_user(is_staff=True, is_superuser=True, password='secret-pass-123')
        self.assertRedirects(self.login(superuser), reverse('admin:index'), fetch_redirect_response=False)

    def test_staff_and_center_members_are_sent_to_the_website(self):
        for user in (make_user(is_staff=True, password='secret-pass-123'),
                     make_membership(user=make_user(is_staff=True, password='secret-pass-123')).user):
            with self.subTest(user=user.email):
                response = self.login(user)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'This page is for platform administrators.')
