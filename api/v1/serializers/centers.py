"""Serializers for centers, their settings and dashboard, and countries."""

from django.utils.translation import gettext_lazy as _
from django_countries import countries
from django_countries.serializer_fields import CountryField
from rest_framework import serializers

from core.models import Center, Language


def center_state(center):
    """
    Where the frontend should route a member of ``center``.

    ``pending_review`` and ``rejected`` come from the review status;
    ``suspended`` is an approved but inactive center; ``operational`` is the
    normal case (dashboard).
    """
    if center.status == Center.Status.PENDING:
        return 'pending_review'
    if center.status == Center.Status.REJECTED:
        return 'rejected'
    return 'operational' if center.is_active else 'suspended'


CENTER_STATES = ['pending_review', 'rejected', 'suspended', 'operational']


class CountrySerializer(serializers.Serializer):
    """An ISO 3166-1 country with its name in the request language."""

    code = serializers.CharField()
    name = serializers.CharField()


class CenterSerializer(serializers.ModelSerializer):
    """A center as its members see it. Identified by ``slug``."""

    country = serializers.SerializerMethodField()
    # Codes, not prose: clients route on these values, so they are not translated.
    state = serializers.SerializerMethodField(help_text='pending_review, rejected, suspended or operational.')

    class Meta:
        model = Center
        fields = [
            'slug', 'name', 'country', 'description', 'contact_email', 'website', 'logo',
            'languages', 'status', 'state', 'rejection_reason', 'is_active', 'created_at',
        ]
        read_only_fields = fields

    def get_country(self, center) -> CountrySerializer(allow_null=True):
        if not center.country:
            return None
        return {'code': center.country.code, 'name': str(center.country.name)}

    def get_state(self, center) -> str:
        return center_state(center)


class CenterSettingsSerializer(serializers.ModelSerializer):
    """
    What a center admin may change. Name, slug and review fields are not editable,
    nor the Telegram group: it is connected only through the bot (ADR 0023).
    """

    country = CountryField(required=False, allow_blank=True)
    languages = serializers.ListField(child=serializers.ChoiceField(choices=Language.choices), required=False)

    class Meta:
        model = Center
        fields = ['slug', 'name', 'country', 'description', 'contact_email', 'website', 'telegram_chat_id', 'languages']
        read_only_fields = ['slug', 'name', 'telegram_chat_id']


class DashboardMembersSerializer(serializers.Serializer):
    """Active member counts."""

    total = serializers.IntegerField()
    center_admins = serializers.IntegerField()
    specialists = serializers.IntegerField()


class DashboardSerializer(serializers.Serializer):
    """Overview of an operational center (response only)."""

    center = CenterSerializer()
    members = DashboardMembersSerializer()


def country_list():
    """All countries, sorted by their name in the active language."""
    return [{'code': code, 'name': str(name)} for code, name in countries]
