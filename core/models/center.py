"""
Centers of specialists, which receive the questions the AI must not answer.

Exactly one center may be the default (ADR 0004): it receives referred
questions when no other center is selected.

Centers that register themselves through the API start ``pending`` and are
approved or rejected by staff through ``core.services.centers`` (ADR 0013).
A center is *operational* when it is approved and active; ``is_active`` keeps
its own meaning, suspending an approved center.
"""

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField

from .base import BaseModel
from .choices import Language


class CenterStatusQuerySet(models.QuerySet):
    """Filters on a center's review status and membership."""

    def operational(self):
        """Return centers that are approved and active: the ones that may work."""
        return self.filter(status=Center.Status.APPROVED, is_active=True)

    def pending(self):
        """Return centers waiting for review."""
        return self.filter(status=Center.Status.PENDING)

    def with_active_member(self, user):
        """Return the centers where ``user`` has an active membership."""
        return self.filter(core_membership__user=user, core_membership__is_active=True).distinct()


class Center(BaseModel):
    """A center of specialists that answers referred questions."""

    class Status(models.TextChoices):
        """Review status. Changed only through ``core.services.centers``."""

        PENDING = 'pending', _('Pending review')
        APPROVED = 'approved', _('Approved')
        REJECTED = 'rejected', _('Rejected')

    name = models.CharField(_('name'), max_length=200, unique=True)
    slug = models.SlugField(_('slug'), max_length=200, unique=True)
    country = CountryField(_('country'), blank=True)
    logo = models.ImageField(_('logo'), upload_to='centers/logos/', blank=True)
    description = models.TextField(_('description'), blank=True)
    contact_email = models.EmailField(_('contact email'), blank=True)
    website = models.URLField(_('website'), blank=True)
    telegram_chat_id = models.BigIntegerField(
        _('Telegram Group ID'),
        null=True,
        blank=True,
        help_text=_(
            'Telegram group where referred questions are sent, for example -1001234567890. '
            'Set when a center admin connects the group through the bot.'
        ),
    )
    languages = ArrayField(
        models.CharField(max_length=2, choices=Language.choices),
        verbose_name=_('languages served'),
        default=list,
        blank=True,
    )
    is_default = models.BooleanField(
        _('default center'),
        default=False,
        help_text=_('Receives referred questions when no other center is selected.'),
    )
    is_active = models.BooleanField(
        _('active'),
        default=True,
        help_text=_('Uncheck to suspend an approved center.'),
    )
    # Admin-created centers are trusted, hence the approved default; self-registered
    # centers are created pending explicitly (core.services.centers.register_center).
    status = models.CharField(
        _('review status'), max_length=10, choices=Status.choices, default=Status.APPROVED,
    )
    reviewed_at = models.DateTimeField(_('reviewed at'), null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name=_('reviewed by'),
    )
    rejection_reason = models.TextField(
        _('rejection reason'),
        blank=True,
        help_text=_('Shown to the applicant.'),
    )

    objects = CenterStatusQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        verbose_name = _('center')
        verbose_name_plural = _('centers')
        constraints = [
            models.UniqueConstraint(
                fields=['is_default'],
                condition=models.Q(is_default=True),
                name='only_one_default_center',
                violation_error_message=_('Only one center can be the default center.'),
            ),
            models.CheckConstraint(
                condition=models.Q(is_default=False) | models.Q(status='approved'),
                name='default_center_must_be_approved',
                violation_error_message=_('Only an approved center can be the default center.'),
            ),
            # One Telegram group per center, and a group serves one center only (ADR 0023)
            models.UniqueConstraint(
                fields=['telegram_chat_id'],
                condition=models.Q(telegram_chat_id__isnull=False),
                name='unique_center_telegram_group',
                violation_error_message=_('This Telegram group is already connected to another center.'),
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def is_operational(self):
        """Whether the center is approved and active."""
        return self.status == self.Status.APPROVED and self.is_active

    def save(self, *args, **kwargs):
        """
        Save the center, refusing an invalid default with a translated error.

        Raises:
            django.core.exceptions.ValidationError: If this center is marked
                default while another one already is, or while it is not
                approved. Checking before the
                write gives callers the constraint's translated message; the
                database constraint still guards against concurrent writes.
                Use ``make_default()`` to move the default.
        """
        if self.is_default:
            self.validate_constraints()
        super().save(*args, **kwargs)

    def make_default(self):
        """
        Make this center the default, unsetting the previous default.

        Runs in one transaction and locks the current default and this row
        with ``SELECT ... FOR UPDATE``, so two concurrent calls cannot leave
        two defaults. The previous default is unset before this row is set,
        which keeps the partial unique constraint satisfied at every step.

        Raises:
            ValidationError: ``center_not_approved`` if the center is not approved.
        """
        if self.status != self.Status.APPROVED:
            raise ValidationError(
                _('Only an approved center can be the default center.'), code='center_not_approved',
            )
        with transaction.atomic():
            locked = list(
                Center.objects.select_for_update().filter(
                    models.Q(is_default=True) | models.Q(pk=self.pk)
                )
            )
            previous = [center.pk for center in locked if center.is_default and center.pk != self.pk]
            if previous:
                # update() bypasses auto_now, so updated_at is set explicitly.
                Center.objects.filter(pk__in=previous).update(
                    is_default=False, updated_at=timezone.now(),
                )
            self.is_default = True
            self.save(update_fields=['is_default', 'updated_at'])
