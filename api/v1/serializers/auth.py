"""Serializers for registration, tokens and the caller's profile."""

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from django_countries import countries
from rest_framework_simplejwt.tokens import RefreshToken

from api.v1.serializers.centers import CenterSerializer

from core.models import Center, Language, User
from core.services import centers


def tokens_for(user):
    """Return a fresh ``{"access", "refresh"}`` pair for ``user``."""
    refresh = RefreshToken.for_user(user)
    return {'access': str(refresh.access_token), 'refresh': str(refresh)}


class UserSerializer(serializers.ModelSerializer):
    """
    The caller's profile. ``uuid`` is the only identifier exposed.

    ``is_platform_admin`` and ``admin_url`` let the frontend send a superuser to
    the Django admin, which only superusers can open (``core.sites``).
    """

    telegram_linked = serializers.SerializerMethodField(
        help_text=_('Whether a Telegram account is linked.'),
    )
    is_platform_admin = serializers.SerializerMethodField(
        help_text=_('True for a platform administrator (superuser): the frontend redirects them to admin_url.'),
    )
    admin_url = serializers.SerializerMethodField(
        help_text=_('Address of the administration site for a platform administrator; null for everyone else.'),
    )

    class Meta:
        model = User
        fields = ['uuid', 'email', 'full_name', 'preferred_lang', 'avatar', 'is_verified', 'telegram_linked',
                  'is_platform_admin', 'admin_url']
        read_only_fields = ['uuid', 'email', 'avatar', 'is_verified']

    def get_telegram_linked(self, user) -> bool:
        return user.telegram_chat_id is not None

    def get_is_platform_admin(self, user) -> bool:
        return user.is_superuser

    def get_admin_url(self, user) -> str | None:
        """``DJANGO_SITE_URL`` + the admin path; without it, the address of the current request."""
        if not user.is_superuser:
            return None
        path = reverse('admin:index')
        if settings.SITE_URL:
            return settings.SITE_URL + path
        request = self.context.get('request')
        return request.build_absolute_uri(path) if request else path


class TokenPairSerializer(serializers.Serializer):
    """An access and a refresh token (response only)."""

    access = serializers.CharField()
    refresh = serializers.CharField()


class AccountFieldsMixin(serializers.Serializer):
    """Fields and checks shared by both registrations."""

    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    preferred_lang = serializers.ChoiceField(choices=Language.choices, default=Language.ENGLISH)

    def validate_email(self, email):
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                _('A user with this email address already exists.'), code='email_taken',
            )
        return email

    def validate(self, attrs):
        # Validators such as UserAttributeSimilarityValidator need the user's data.
        candidate = User(email=attrs['email'], full_name=attrs['full_name'])
        try:
            validate_password(attrs['password'], candidate)
        except DjangoValidationError as error:
            # Keep each password validator's message and code.
            raise serializers.ValidationError({'password': [
                serializers.ErrorDetail(e.messages[0], e.code or 'invalid_password')
                for e in error.error_list
            ]}) from error
        return attrs

    def create_user(self, attrs):
        return User.objects.create_user(
            attrs['email'], attrs['full_name'], password=attrs['password'],
            preferred_lang=attrs['preferred_lang'],
        )


class RegistrationSerializer(AccountFieldsMixin):
    """Register an asker: a plain account, logged in on success."""

    def create(self, validated_data):
        return self.create_user(validated_data)

    def to_representation(self, user):
        return {'user': UserSerializer(user, context=self.context).data, **tokens_for(user)}


class RegistrationResponseSerializer(serializers.Serializer):
    """Response of both registrations (schema only)."""

    user = UserSerializer()
    access = serializers.CharField()
    refresh = serializers.CharField()


class CenterApplicationSerializer(serializers.Serializer):
    """The center part of a center registration."""

    name = serializers.CharField(max_length=200)
    country = serializers.CharField(max_length=2, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    website = serializers.URLField(required=False, allow_blank=True)
    languages = serializers.ListField(
        child=serializers.ChoiceField(choices=Language.choices), required=False,
    )

    def validate_name(self, name):
        if Center.objects.filter(name__iexact=name).exists():
            raise serializers.ValidationError(
                _('A center with this name already exists.'), code='center_name_taken',
            )
        return name

    def validate_country(self, country):
        if country and country.upper() not in countries:
            raise serializers.ValidationError(_('Unknown country code.'), code='invalid_country')
        return country.upper()


class CenterRegistrationSerializer(AccountFieldsMixin):
    """
    Register an account and a center in one step.

    The center is created pending review and the new account becomes its
    center admin (``core.services.centers.register_center``).
    """

    center = CenterApplicationSerializer()

    def create(self, validated_data):
        center_fields = validated_data.pop('center')
        with transaction.atomic():
            user = self.create_user(validated_data)
            self._center = centers.register_center(user, **center_fields)
        return user

    def to_representation(self, user):
        return {
            'user': UserSerializer(user, context=self.context).data,
            'center': CenterSerializer(self._center, context=self.context).data,
            **tokens_for(user),
        }


class CenterRegistrationResponseSerializer(RegistrationResponseSerializer):
    """Response of a center registration (schema only)."""

    center = CenterSerializer()
