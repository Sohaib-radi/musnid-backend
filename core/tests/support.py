"""
Shared test helpers: object factories and test-only models.

Factories give every object unique defaults, so tests only spell out the
fields they are about. Tests create objects through these factories, never
through ``objects.create()`` directly, so a new required field is added in
one place.

``Note`` is a concrete model used only by tests, to exercise the abstract
building blocks in ``core.models.base``. It has no migration; its table is
created by ``core.tests.runner.TestRunner`` when the test database is built.
Every such model must be listed in ``TEST_ONLY_MODELS``.
"""

import itertools

from django.db import models

from core.models import (
    BaseModel, Center, CenterLinkedModel, CreatedByMixin, Membership, User,
)

_sequence = itertools.count(1)


class Note(BaseModel, CenterLinkedModel, CreatedByMixin):
    """Test-only model combining every abstract building block."""

    title = models.CharField(max_length=100)

    class Meta(BaseModel.Meta):
        app_label = 'core'
        db_table = 'core_test_note'


TEST_ONLY_MODELS = [Note]


def make_user(**fields):
    """
    Create a user with a unique email and name.

    The password is unusable unless ``password`` is given: hashing is slow and
    most tests never log in.
    """
    n = next(_sequence)
    fields.setdefault('email', f'user{n}@example.com')
    fields.setdefault('full_name', f'User {n}')
    return User.objects.create_user(**fields)


def make_center(**fields):
    """Create an active, non-default center with a unique name and slug."""
    n = next(_sequence)
    fields.setdefault('name', f'Center {n}')
    fields.setdefault('slug', f'center-{n}')
    return Center.objects.create(**fields)


def make_membership(**fields):
    """
    Create an active specialist membership.

    A new user and a new center are created unless given.
    """
    if 'user' not in fields:
        fields['user'] = make_user()
    if 'center' not in fields:
        fields['center'] = make_center()
    fields.setdefault('role', Membership.Role.SPECIALIST)
    return Membership.objects.create(**fields)


def make_note(**fields):
    """Create a ``Note`` in a new center unless one is given."""
    if 'center' not in fields:
        fields['center'] = make_center()
    fields.setdefault('title', f'Note {next(_sequence)}')
    return Note.objects.create(**fields)
