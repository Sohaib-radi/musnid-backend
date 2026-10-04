"""
Tests for the abstract building blocks in ``core.models.base``.

They use the test-only ``Note`` model (``core.tests.support``), which combines
``BaseModel``, ``CenterLinkedModel`` and ``CreatedByMixin``.
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.models import Center
from core.tests.support import Note, make_center, make_note, make_user


class BaseModelTests(TestCase):
    """Timestamps and default ordering."""

    def test_timestamps_are_set_on_create(self):
        before = timezone.now()
        note = make_note()
        self.assertGreaterEqual(note.created_at, before)
        self.assertGreaterEqual(note.updated_at, note.created_at)

    def test_updated_at_changes_on_save_and_created_at_does_not(self):
        note = make_note()
        created_at, updated_at = note.created_at, note.updated_at
        note.title = 'Changed'
        note.save()
        note.refresh_from_db()
        self.assertEqual(note.created_at, created_at)
        self.assertGreater(note.updated_at, updated_at)

    def test_default_ordering_is_newest_first(self):
        center = make_center()
        older = make_note(center=center)
        newer = make_note(center=center)
        Note.objects.filter(pk=older.pk).update(created_at=timezone.now() - timedelta(days=1))
        self.assertEqual(list(Note.objects.all()), [newer, older])

    def test_subclass_meta_inherits_ordering(self):
        self.assertEqual(Note._meta.ordering, ['-created_at'])
        self.assertFalse(Note._meta.abstract)

    def test_created_at_is_indexed(self):
        self.assertTrue(Note._meta.get_field('created_at').db_index)


class CenterLinkedModelTests(TestCase):
    """Center ownership, explicit scoping and cascade deletion."""

    def test_for_center_returns_only_that_centers_rows(self):
        center, other = make_center(), make_center()
        mine = make_note(center=center)
        make_note(center=other)
        self.assertEqual(list(Note.objects.for_center(center)), [mine])

    def test_for_center_accepts_a_primary_key(self):
        center = make_center()
        mine = make_note(center=center)
        make_note()
        self.assertEqual(list(Note.objects.for_center(center.pk)), [mine])

    def test_for_center_rejects_none_and_unsaved_centers(self):
        for center in (None, Center(name='Unsaved', slug='unsaved')):
            with self.subTest(center=center), self.assertRaises(ValueError):
                Note.objects.for_center(center)

    def test_default_manager_is_not_scoped(self):
        make_note()
        make_note()
        self.assertEqual(Note.objects.count(), 2)

    def test_reverse_accessor_and_query_name(self):
        center = make_center()
        note = make_note(center=center)
        self.assertEqual(list(center.core_note_set.all()), [note])
        self.assertEqual(list(Center.objects.filter(core_note__title=note.title)), [center])

    def test_deleting_the_center_deletes_its_rows(self):
        note = make_note()
        note.center.delete()
        self.assertFalse(Note.objects.filter(pk=note.pk).exists())


class CreatedByMixinTests(TestCase):
    """The creator link is optional and survives the user's deletion as NULL."""

    def test_created_by_is_optional(self):
        self.assertIsNone(make_note().created_by)

    def test_deleting_the_user_keeps_the_row(self):
        user = make_user()
        note = make_note(created_by=user)
        user.delete()
        note.refresh_from_db()
        self.assertIsNone(note.created_by)

    def test_no_reverse_accessor_on_user(self):
        field = Note._meta.get_field('created_by')
        self.assertTrue(field.remote_field.hidden)
