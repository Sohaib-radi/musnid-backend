"""
Managing who belongs to a center and with which role.

Rules enforced here, each reported as a ``ValidationError`` with a code:

* ``user_not_found``: no user has the given email.
* ``user_inactive``: the user exists but is deactivated.
* ``invalid_role``: the role is not a ``Membership.Role`` value.
* ``already_member``: the user already has an active membership of the center.
* ``membership_inactive``: the membership was already ended.
* ``last_center_admin``: the change would leave the center without an active
  center admin.

The last rule protects centers that have an admin. A new center starts with
none; ``add_member`` does not require one, so the first admin can be added.

``validate_add_member`` and ``validate_change_role`` run the same checks
without changing anything, so forms can report problems as form errors. They
read without locks; the mutating functions check again under row locks, which
is what makes the rules hold under concurrency.

Members leave by deactivation (``is_active=False`` and ``left_at`` set), never
by deletion, so the history is kept and the user can rejoin later with a new
membership.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import Membership, User


def add_member(center, email, role):
    """
    Add an existing, active user to ``center`` with ``role``.

    Args:
        center: The ``Center`` to join.
        email: Email of the user, matched case-insensitively.
        role: A ``Membership.Role`` value.

    Returns:
        The new ``Membership``.

    Raises:
        ValidationError: ``invalid_role``, ``user_not_found``, ``user_inactive``
            or ``already_member``.
    """
    _check_role(role)
    user = User.objects.filter(email__iexact=email.strip()).first()
    if user is None:
        raise ValidationError(_('No user exists with this email address.'), code='user_not_found')
    _check_user_active(user)

    with transaction.atomic():
        # Lock the user's row so two concurrent calls for the same user cannot
        # both pass the check below; unique_active_membership is the backstop.
        User.objects.select_for_update().filter(pk=user.pk).get()
        _check_not_member(center, user)
        return Membership.objects.create(center=center, user=user, role=role)


def validate_add_member(center, user, role):
    """
    Check that ``add_member`` would accept ``user``, without saving.

    Args:
        center: The ``Center`` to join.
        user: The ``User`` to add.
        role: A ``Membership.Role`` value.

    Raises:
        ValidationError: ``invalid_role``, ``user_inactive`` or ``already_member``.
    """
    _check_role(role)
    _check_user_active(user)
    _check_not_member(center, user)


def change_role(membership, role):
    """
    Change the role of an active membership.

    Args:
        membership: The ``Membership`` to change.
        role: The new ``Membership.Role`` value. The same role is a no-op.

    Returns:
        The updated ``Membership``.

    Raises:
        ValidationError: ``invalid_role``, ``membership_inactive`` or
            ``last_center_admin`` (demoting the only active center admin).
    """
    _check_role(role)
    with transaction.atomic():
        membership, admins = _lock_active(membership)
        if membership.role == role:
            return membership
        if membership.role == Membership.Role.CENTER_ADMIN:
            _ensure_another_admin(membership, admins)
        membership.role = role
        membership.save(update_fields=['role', 'updated_at'])
        return membership


def validate_change_role(membership, role):
    """
    Check that ``change_role`` would accept ``role``, without saving.

    The membership's current state is read from the database, so it does not
    matter whether ``membership`` was already modified in memory (as a bound
    form's instance is).

    Raises:
        ValidationError: ``invalid_role``, ``membership_inactive`` or
            ``last_center_admin``.
    """
    _check_role(role)
    current = Membership.objects.get(pk=membership.pk)
    if not current.is_active:
        raise ValidationError(_('This membership has already ended.'), code='membership_inactive')
    if current.role == Membership.Role.CENTER_ADMIN and role != current.role:
        admins = list(Membership.objects.for_center(current.center_id).active().center_admins())
        _ensure_another_admin(current, admins)


def offboard(membership):
    """
    End a membership: deactivate it and record when the user left.

    Args:
        membership: The active ``Membership`` to end.

    Returns:
        The updated ``Membership``.

    Raises:
        ValidationError: ``membership_inactive`` or ``last_center_admin``
            (offboarding the only active center admin).
    """
    with transaction.atomic():
        membership, admins = _lock_active(membership)
        if membership.role == Membership.Role.CENTER_ADMIN:
            _ensure_another_admin(membership, admins)
        membership.is_active = False
        membership.left_at = timezone.now()
        membership.save(update_fields=['is_active', 'left_at', 'updated_at'])
        return membership


def _check_role(role):
    if role not in Membership.Role.values:
        raise ValidationError(
            _('“%(role)s” is not a valid role.'), code='invalid_role', params={'role': role},
        )


def _check_user_active(user):
    if not user.is_active:
        raise ValidationError(_('This user account is deactivated.'), code='user_inactive')


def _check_not_member(center, user):
    if Membership.objects.for_center(center).active().filter(user=user).exists():
        raise ValidationError(
            _('This user is already an active member of this center.'), code='already_member',
        )


def _lock_active(membership):
    """
    Lock and reload ``membership`` and its center's active admins.

    The admins are locked first, in primary key order, then the membership.
    A fixed order means concurrent calls on the same center wait for each
    other instead of deadlocking, and the admin list stays valid until the
    transaction commits.

    Returns:
        A tuple ``(membership, admins)``: the reloaded membership and the
        list of the center's active center admin memberships.

    Raises:
        ValidationError: ``membership_inactive`` if the membership has ended.
    """
    admins = list(
        Membership.objects.select_for_update()
        .for_center(membership.center_id)
        .active()
        .center_admins()
        .order_by('pk')
    )
    locked = Membership.objects.select_for_update().get(pk=membership.pk)
    if not locked.is_active:
        raise ValidationError(_('This membership has already ended.'), code='membership_inactive')
    return locked, admins


def _ensure_another_admin(membership, admins):
    """Raise ``last_center_admin`` unless ``admins`` holds someone besides ``membership``."""
    if not any(admin.pk != membership.pk for admin in admins):
        raise ValidationError(
            _('A center must keep at least one active center admin.'), code='last_center_admin',
        )
