"""
Center registration and review (ADR 0013).

A center registered through the API starts ``pending``; its applicant becomes
its center admin. Staff review it: ``approve`` or ``reject`` (with a reason
shown to the applicant). Only pending centers can be reviewed, and the status
is never edited directly. Rules are reported as ``ValidationError`` with a code:

* ``center_not_pending``: the center was already reviewed.
* ``rejection_reason_required``: a rejection without a reason.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from core.models import Center, Membership
from core.services import memberships


def register_center(applicant, **fields):
    """
    Create a pending center with ``applicant`` as its center admin.

    Args:
        applicant: The active ``User`` applying for the center.
        **fields: ``Center`` fields (``name`` required). ``status`` and review
            fields are ignored; ``slug`` is derived from the name when omitted.

    Returns:
        The new ``Center``.
    """
    for protected in ('status', 'reviewed_at', 'reviewed_by', 'rejection_reason', 'is_default'):
        fields.pop(protected, None)
    with transaction.atomic():
        fields.setdefault('slug', unique_slug(fields['name']))
        center = Center.objects.create(status=Center.Status.PENDING, **fields)
        memberships.add_member(center, applicant.email, Membership.Role.CENTER_ADMIN)
    return center


def approve(center, reviewer):
    """
    Approve a pending center.

    Raises:
        ValidationError: ``center_not_pending``.
    """
    return _review(center, reviewer, Center.Status.APPROVED, reason='')


def reject(center, reviewer, reason):
    """
    Reject a pending center with a reason shown to the applicant.

    Raises:
        ValidationError: ``rejection_reason_required`` or ``center_not_pending``.
    """
    reason = (reason or '').strip()
    if not reason:
        raise ValidationError(
            _('A reason is required to reject a center.'), code='rejection_reason_required',
        )
    return _review(center, reviewer, Center.Status.REJECTED, reason=reason)


def unique_slug(name):
    """
    Return a slug for ``name`` that no center uses yet.

    Arabic names have no ASCII slug, so they fall back to ``center``; a number
    is appended until the slug is free.
    """
    base = slugify(name)[:190] or 'center'
    slug, number = base, 2
    while Center.objects.filter(slug=slug).exists():
        slug, number = f'{base}-{number}', number + 1
    return slug


def _review(center, reviewer, status, reason):
    with transaction.atomic():
        locked = Center.objects.select_for_update().get(pk=center.pk)
        if locked.status != Center.Status.PENDING:
            raise ValidationError(_('Only a pending center can be reviewed.'), code='center_not_pending')
        locked.status = status
        locked.rejection_reason = reason
        locked.reviewed_by = reviewer
        locked.reviewed_at = timezone.now()
        locked.save(update_fields=['status', 'rejection_reason', 'reviewed_by', 'reviewed_at', 'updated_at'])
    center.refresh_from_db()
    return center
