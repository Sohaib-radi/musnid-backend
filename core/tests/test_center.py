"""Tests for ``core.models.center``: centers and the single default center."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import translation

from core.models import Center, Language
from core.tests.support import make_center


class CenterModelTests(TestCase):
    """Fields, defaults and uniqueness."""

    def test_defaults(self):
        center = make_center()
        self.assertTrue(center.is_active)
        self.assertFalse(center.is_default)
        self.assertEqual(center.languages, [])
        self.assertIsNone(center.telegram_chat_id)
        self.assertEqual(str(center), center.name)

    def test_country_is_stored_as_iso_code(self):
        center = make_center(country='MA')
        center.refresh_from_db()
        self.assertEqual(center.country.code, 'MA')

    def test_languages_round_trip(self):
        center = make_center(languages=[Language.ARABIC, Language.FRENCH])
        center.refresh_from_db()
        self.assertEqual(center.languages, ['ar', 'fr'])

    def test_full_clean_rejects_unknown_language(self):
        center = make_center()
        center.languages = ['de']
        with self.assertRaises(ValidationError):
            center.full_clean()

    def test_name_and_slug_are_unique(self):
        make_center(name='Dar al-Ifta', slug='dar-al-ifta')
        for fields in ({'name': 'Dar al-Ifta'}, {'slug': 'dar-al-ifta'}):
            with self.subTest(fields=fields), self.assertRaises(IntegrityError), transaction.atomic():
                make_center(**fields)

    def test_telegram_group_id_label(self):
        field = Center._meta.get_field('telegram_chat_id')
        self.assertEqual(str(field.verbose_name), 'Telegram Group ID')
        self.assertIn('-1001234567890', str(field.help_text))


class DefaultCenterTests(TestCase):
    """At most one default center, and ``make_default`` to move it."""

    def test_one_default_is_allowed(self):
        self.assertTrue(make_center(is_default=True).is_default)

    def test_second_default_is_refused_with_constraint_message(self):
        make_center(is_default=True)
        with self.assertRaises(ValidationError) as caught:
            make_center(is_default=True)
        self.assertEqual(caught.exception.messages, ['Only one center can be the default center.'])

    def test_violation_message_is_translated(self):
        make_center(is_default=True)
        for language, expected in (
            ('ar', 'يمكن أن يكون مركز واحد فقط هو المركز الافتراضي.'),
            ('fr', 'Un seul centre peut être le centre par défaut.'),
        ):
            with self.subTest(language=language), translation.override(language):
                with self.assertRaises(ValidationError) as caught:
                    make_center(is_default=True)
                self.assertEqual(caught.exception.messages, [expected])

    def test_database_constraint_backs_the_check(self):
        make_center(is_default=True)
        other = make_center()
        # update() skips save(), so only the database constraint can stop it.
        with self.assertRaises(IntegrityError) as caught, transaction.atomic():
            Center.objects.filter(pk=other.pk).update(is_default=True)
        self.assertIn('only_one_default_center', str(caught.exception))

    def test_resaving_the_default_is_allowed(self):
        center = make_center(is_default=True)
        center.description = 'Updated'
        center.save()
        self.assertTrue(Center.objects.get(pk=center.pk).is_default)

    def test_make_default_moves_the_default(self):
        old = make_center(is_default=True)
        new = make_center()
        old_updated_at = old.updated_at
        new.make_default()
        old.refresh_from_db()
        new.refresh_from_db()
        self.assertFalse(old.is_default)
        self.assertTrue(new.is_default)
        self.assertGreater(old.updated_at, old_updated_at)
        self.assertEqual(Center.objects.filter(is_default=True).count(), 1)

    def test_make_default_without_previous_default(self):
        center = make_center()
        center.make_default()
        self.assertTrue(Center.objects.get(pk=center.pk).is_default)

    def test_make_default_on_the_default_is_a_no_op(self):
        center = make_center(is_default=True)
        center.make_default()
        self.assertEqual(list(Center.objects.filter(is_default=True)), [center])


class ReviewStatusTests(TestCase):
    """Review status, operational centers and the approved-default rule."""

    def test_admin_created_centers_default_to_approved(self):
        self.assertEqual(make_center().status, Center.Status.APPROVED)

    def test_operational_means_approved_and_active(self):
        operational = make_center()
        make_center(is_active=False)
        make_center(status=Center.Status.PENDING)
        make_center(status=Center.Status.REJECTED)
        self.assertEqual(list(Center.objects.operational()), [operational])
        self.assertTrue(operational.is_operational)

    def test_pending(self):
        pending = make_center(status=Center.Status.PENDING)
        make_center()
        self.assertEqual(list(Center.objects.pending()), [pending])

    def test_default_center_must_be_approved(self):
        with self.assertRaises(ValidationError) as caught:
            make_center(status=Center.Status.PENDING, is_default=True)
        self.assertEqual(caught.exception.messages, ['Only an approved center can be the default center.'])
        center = make_center(status=Center.Status.PENDING)
        with self.assertRaises(IntegrityError) as caught, transaction.atomic():
            Center.objects.filter(pk=center.pk).update(is_default=True)
        self.assertIn('default_center_must_be_approved', str(caught.exception))

    def test_make_default_refuses_a_non_approved_center(self):
        center = make_center(status=Center.Status.PENDING)
        with self.assertRaises(ValidationError) as caught:
            center.make_default()
        self.assertEqual(caught.exception.code, 'center_not_approved')
        self.assertFalse(Center.objects.filter(is_default=True).exists())


class TelegramGroupConstraintTests(TestCase):
    """``unique_center_telegram_group``: a Telegram group serves one center (ADR 0023)."""

    def test_a_group_cannot_serve_two_centers(self):
        make_center(telegram_chat_id=-100)
        make_center(telegram_chat_id=None)
        make_center(telegram_chat_id=None)  # many centers without a group
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_center(telegram_chat_id=-100)
