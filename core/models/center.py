"""
Centers of specialists, which receive the questions the AI must not answer.

Exactly one center may be the default (ADR 0004): it receives referred
questions when no other center is selected.
"""

from django.contrib.postgres.fields import ArrayField
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField

from .base import BaseModel
from .choices import Language


class Center(BaseModel):
    """A center of specialists that answers referred questions."""

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
            'Telegram group where referred questions are sent, for example -1001234567890.'
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
    is_active = models.BooleanField(_('active'), default=True)

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
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """
        Save the center, refusing a second default with a translated error.

        Raises:
            django.core.exceptions.ValidationError: If this center is marked
                default while another one already is. Checking before the
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
        """
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
