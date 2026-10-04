"""Serializers for memberships: listing, adding by email, changing role."""

from rest_framework import serializers

from api.v1.serializers.centers import CenterSerializer
from core.models import Membership, User
from core.services import memberships


class MemberSerializer(serializers.ModelSerializer):
    """The public part of a member's account."""

    class Meta:
        model = User
        fields = ['uuid', 'email', 'full_name']
        read_only_fields = fields


class MembershipSerializer(serializers.ModelSerializer):
    """A membership as center admins see it. Identified by ``uuid``."""

    user = MemberSerializer(read_only=True)

    class Meta:
        model = Membership
        fields = ['uuid', 'user', 'role', 'is_active', 'created_at', 'left_at']
        read_only_fields = fields


class MyMembershipSerializer(serializers.ModelSerializer):
    """One of the caller's memberships, with the center's status for routing."""

    center = CenterSerializer(read_only=True)

    class Meta:
        model = Membership
        fields = ['uuid', 'role', 'is_active', 'created_at', 'left_at', 'center']
        read_only_fields = fields


class AddMemberSerializer(serializers.Serializer):
    """Add an existing user to the center by email (``add_member``)."""

    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=Membership.Role.choices)

    def create(self, validated_data):
        return memberships.add_member(self.context['center'], validated_data['email'], validated_data['role'])

    def to_representation(self, membership):
        return MembershipSerializer(membership, context=self.context).data


class ChangeRoleSerializer(serializers.Serializer):
    """Change a membership's role (``change_role``)."""

    role = serializers.ChoiceField(choices=Membership.Role.choices)

    def update(self, membership, validated_data):
        return memberships.change_role(membership, validated_data['role'])

    def to_representation(self, membership):
        return MembershipSerializer(membership, context=self.context).data
