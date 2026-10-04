"""Membership endpoints of a center: list, add by email, change role, offboard. No DELETE."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsCenterAdmin, IsOperationalCenter
from api.v1.serializers.memberships import AddMemberSerializer, ChangeRoleSerializer, MembershipSerializer
from api.v1.views.mixins import CenterScopedMixin
from core.models import Membership
from core.services import memberships

CENTER_ADMIN_PERMISSIONS = [permissions.IsAuthenticated, IsCenterAdmin, IsOperationalCenter]


class MembershipScopedMixin(CenterScopedMixin):
    """Memberships of the URL's center only; the membership is found by ``uuid``."""

    permission_classes = CENTER_ADMIN_PERMISSIONS

    def get_queryset(self):
        return Membership.objects.for_center(self.get_center()).select_related('user')

    def get_object(self):
        return get_object_or_404(self.get_queryset(), uuid=self.kwargs['uuid'])

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'center': self.get_center()}


@extend_schema(tags=['memberships'])
class MembershipListView(MembershipScopedMixin, generics.ListCreateAPIView):
    """List the center's memberships (active first) or add a member by email."""

    def get_queryset(self):
        return super().get_queryset().order_by('-is_active', '-created_at')

    def get_serializer_class(self):
        return AddMemberSerializer if self.request.method == 'POST' else MembershipSerializer

    @extend_schema(request=AddMemberSerializer, responses={201: MembershipSerializer})
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


@extend_schema(tags=['memberships'])
class MembershipDetailView(MembershipScopedMixin, generics.RetrieveUpdateAPIView):
    """Read a membership, or change its role with PATCH."""

    http_method_names = ['get', 'patch', 'head', 'options']

    def get_serializer_class(self):
        return ChangeRoleSerializer if self.request.method == 'PATCH' else MembershipSerializer

    @extend_schema(request=ChangeRoleSerializer, responses=MembershipSerializer)
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


@extend_schema(tags=['memberships'], request=None, responses=MembershipSerializer)
class MembershipOffboardView(MembershipScopedMixin, APIView):
    """End a membership (deactivate, record the leaving date). Never deletes."""

    def post(self, request, slug, uuid):
        membership = memberships.offboard(self.get_object())
        return Response(MembershipSerializer(membership).data, status=status.HTTP_200_OK)
