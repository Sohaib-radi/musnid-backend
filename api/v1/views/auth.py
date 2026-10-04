"""Account endpoints: registration, tokens, the caller's profile and memberships."""

from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions
from rest_framework_simplejwt import views as jwt_views
from rest_framework_simplejwt.authentication import JWTAuthentication

from api.v1.serializers.auth import (
    CenterRegistrationResponseSerializer, CenterRegistrationSerializer, RegistrationResponseSerializer,
    RegistrationSerializer, UserSerializer,
)
from api.v1.serializers.memberships import MyMembershipSerializer
from core.models import Membership


class RegisterView(generics.CreateAPIView):
    """Create an asker account. Returns the user and a token pair."""

    serializer_class = RegistrationSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'auth'

    @extend_schema(responses={201: RegistrationResponseSerializer}, tags=['auth'])
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class CenterRegisterView(generics.CreateAPIView):
    """Create an account and a center pending review; the account becomes its center admin."""

    serializer_class = CenterRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'auth'

    @extend_schema(responses={201: CenterRegistrationResponseSerializer}, tags=['auth'])
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


@extend_schema(tags=['auth'])
class LoginView(jwt_views.TokenObtainPairView):
    """Exchange email and password for an access and a refresh token."""

    throttle_scope = 'auth'


@extend_schema(tags=['auth'])
class RefreshView(jwt_views.TokenRefreshView):
    """Exchange a refresh token for a new pair; the old refresh token is blacklisted."""

    throttle_scope = 'auth'


@extend_schema(tags=['auth'])
class LogoutView(jwt_views.TokenBlacklistView):
    """Blacklist a refresh token. Requires an access token."""

    # SimpleJWT's token views disable authentication; logout must know the caller.
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]


@extend_schema(tags=['me'])
class MeView(generics.RetrieveUpdateAPIView):
    """The caller's profile. PATCH changes full_name and preferred_lang."""

    serializer_class = UserSerializer
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_object(self):
        return self.request.user


@extend_schema(tags=['me'])
class MyMembershipsView(generics.ListAPIView):
    """The caller's memberships, active first, each with its center's status."""

    serializer_class = MyMembershipSerializer

    def get_queryset(self):
        return (
            Membership.objects.filter(user=self.request.user)
            .select_related('center').order_by('-is_active', '-created_at')
        )
