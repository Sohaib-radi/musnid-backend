"""
The custom user model, identified by email (ADR 0002, ADR 0006).

The integer primary key is internal. Anything exposed outside the backend
(URLs, API payloads, Telegram callbacks) must use ``uuid``.
"""

import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from .base import BaseModel
from .choices import Language


class UserManager(BaseUserManager):
    """Creates users and looks them up by email, ignoring case."""

    use_in_migrations = True

    def get_by_natural_key(self, email):
        """
        Return the user whose email matches ``email`` case-insensitively.

        ``ModelBackend`` calls this to authenticate, so this override is what
        makes login case-insensitive. The ``unique_user_email_ci`` constraint
        guarantees at most one match.
        """
        return self.get(email__iexact=email)

    def _create_user(self, email, full_name, password, **extra_fields):
        if not email:
            raise ValueError('The email address is required.')
        user = self.model(email=self.normalize_email(email), full_name=full_name, **extra_fields)
        # None stores an unusable password: the account exists but cannot log
        # in with a password until one is set.
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, full_name, password=None, **extra_fields):
        """
        Create and return a regular user.

        Args:
            email: Login identifier. The domain part is lower-cased.
            full_name: Display name.
            password: Raw password, or ``None`` for an unusable password.
            **extra_fields: Any other ``User`` field.
        """
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, full_name, password, **extra_fields)

    def create_superuser(self, email, full_name, password=None, **extra_fields):
        """
        Create and return a superuser (``is_staff`` and ``is_superuser`` set).

        Raises:
            ValueError: If ``is_staff`` or ``is_superuser`` is passed as false.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields['is_staff'] is not True:
            raise ValueError('A superuser must have is_staff=True.')
        if extra_fields['is_superuser'] is not True:
            raise ValueError('A superuser must have is_superuser=True.')
        return self._create_user(email, full_name, password, **extra_fields)


class User(BaseModel, AbstractBaseUser, PermissionsMixin):
    """
    A person who logs in: specialists, center administrators, staff.

    Email is the login identifier and is unique regardless of case.
    ``telegram_chat_id`` is set when a specialist links their Telegram account
    so the platform can message them directly.
    """

    uuid = models.UUIDField(
        _('public identifier'), default=uuid.uuid4, unique=True, editable=False,
    )
    email = models.EmailField(
        _('email address'),
        unique=True,
        error_messages={'unique': _('A user with this email address already exists.')},
    )
    full_name = models.CharField(_('full name'), max_length=150)
    preferred_lang = models.CharField(
        _('preferred language'),
        max_length=2,
        choices=Language.choices,
        default=Language.ENGLISH,
    )
    avatar = models.ImageField(_('avatar'), upload_to='users/avatars/', blank=True)
    telegram_chat_id = models.BigIntegerField(
        _('Telegram chat ID'),
        unique=True,
        null=True,
        blank=True,
        help_text=_('Set when the user links their Telegram account.'),
    )
    is_active = models.BooleanField(
        _('active'),
        default=True,
        help_text=_('Inactive users cannot log in. Deactivate accounts instead of deleting them.'),
    )
    is_staff = models.BooleanField(
        _('staff status'),
        default=False,
        help_text=_('Whether the user can log in to the administration site.'),
    )
    is_verified = models.BooleanField(
        _('email verified'),
        default=False,
        help_text=_('Whether the user has confirmed their email address.'),
    )

    objects = UserManager()

    USERNAME_FIELD = 'email'
    EMAIL_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    class Meta(BaseModel.Meta):
        verbose_name = _('user')
        verbose_name_plural = _('users')
        constraints = [
            models.UniqueConstraint(
                Lower('email'),
                name='unique_user_email_ci',
                violation_error_message=_('A user with this email address already exists.'),
            ),
        ]

    def __str__(self):
        return self.email

    def clean(self):
        """Normalise the email the same way ``UserManager`` does on creation."""
        super().clean()
        self.email = type(self).objects.normalize_email(self.email)

    def get_full_name(self):
        """Return the user's full name."""
        return self.full_name

    def get_short_name(self):
        """Return the user's full name; there is no separate short name."""
        return self.full_name
