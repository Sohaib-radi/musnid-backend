"""Center endpoints: detail, dashboard and settings of the caller's centers; countries."""

from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsCenterAdmin, IsCenterMember, IsOperationalCenter
from api.v1.serializers.centers import (
    CenterSerializer, CenterSettingsSerializer, CountrySerializer, DashboardSerializer, country_list,
)
from api.v1.views.mixins import CenterScopedMixin
from core.models import Membership


@extend_schema(tags=['centers'])
class CenterDetailView(CenterScopedMixin, generics.RetrieveAPIView):
    """A center the caller belongs to, whatever its review status."""

    serializer_class = CenterSerializer
    permission_classes = [permissions.IsAuthenticated, IsCenterMember]

    def get_object(self):
        return self.get_center()


@extend_schema(tags=['centers'], responses=DashboardSerializer)
class CenterDashboardView(CenterScopedMixin, APIView):
    """Overview for center admins of an operational center."""

    permission_classes = [permissions.IsAuthenticated, IsCenterAdmin, IsOperationalCenter]

    def get(self, request, slug):
        center = self.get_center()
        active = Membership.objects.for_center(center).active()
        data = {
            'center': center,
            'members': {
                'total': active.count(),
                'center_admins': active.center_admins().count(),
                'specialists': active.specialists().count(),
            },
        }
        return Response(DashboardSerializer(data, context={'request': request}).data)


@extend_schema(tags=['centers'])
class CenterSettingsView(CenterScopedMixin, generics.RetrieveUpdateAPIView):
    """Read and change an operational center's settings (center admins)."""

    serializer_class = CenterSettingsSerializer
    permission_classes = [permissions.IsAuthenticated, IsCenterAdmin, IsOperationalCenter]
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_object(self):
        return self.get_center()


@extend_schema(tags=['countries'], responses=CountrySerializer(many=True))
class CountryListView(APIView):
    """Every country with its name in the request language (public)."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response(country_list())
