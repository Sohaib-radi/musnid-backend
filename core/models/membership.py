"""
Membership: the link between a user and a center, with a role (ADR 0007).

Memberships are deactivated, never deleted, when a user leaves a center, so
the history of who belonged where is kept. Business rules that involve
several memberships (for example "a center keeps at least one admin") live in
``core.services.memberships``.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from .base import BaseModel, CenterLinkedModel, CenterQuerySet


class MembershipQuerySet(CenterQuerySet):
    """
    Filters for memberships. Each method applies one condition, so they
    combine freely, e.g. ``Membership.objects.for_center(c).active().center_admins()``.
    """

    def active(self):
        """Return memberships that are currently active."""
        return self.filter(is_active=True)

    def center_admins(self):
        """Return memberships with the center admin role, active or not."""
        return self.filter(role=Membership.Role.CENTER_ADMIN)

    def specialists(self):
        """Return memberships with the specialist role, active or not."""
        return self.filter(role=Membership.Role.SPECIALIST)


class Membership(BaseModel, CenterLinkedModel):
    """
    A user's membership of one center, with a role.

    A user has at most one active membership per center. An inactive
    membership records when the user left (``left_at``); the database enforces
    that ``is_active`` and ``left_at`` agree.
    """

    class Role(models.TextChoices):
        """What a member may do within the center."""

        SPECIALIST = 'specialist', _('Specialist')
        CENTER_ADMIN = 'center_admin', _('Center admin')

    uuid = models.UUIDField(
        _('public identifier'), default=uuid.uuid4, unique=True, editable=False,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='memberships',
        verbose_name=_('user'),
    )
    role = models.CharField(_('role'), max_length=20, choices=Role.choices)
    is_active = models.BooleanField(_('active'), default=True)
    left_at = models.DateTimeField(_('left at'), null=True, blank=True)

    objects = MembershipQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        verbose_name = _('membership')
        verbose_name_plural = _('memberships')
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'center'],
                condition=models.Q(is_active=True),
                name='unique_active_membership',
                violation_error_message=_('This user is already an active member of this center.'),
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(is_active=True, left_at__isnull=True)
                    | models.Q(is_active=False, left_at__isnull=False)
                ),
                name='membership_active_matches_left_at',
                violation_error_message=_(
                    'An active membership cannot have a leaving date, '
                    'and an inactive membership must have one.'
                ),
            ),
        ]

    def __str__(self):
        return f'{self.user} – {self.center} ({self.get_role_display()})'
