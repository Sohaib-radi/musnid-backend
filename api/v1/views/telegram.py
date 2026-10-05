"""
Telegram connection of a center (ADR 0023).

The dashboard's "Connect to Telegram" button calls ``POST telegram/connect/``
and opens the returned ``startgroup`` link; while the center admin picks the
group in Telegram, the page polls ``GET telegram/`` and shows a spinner until
``connected`` is true. "Disconnect" calls ``POST telegram/disconnect/``. Views stay thin: the rules are in ``telegram_bot.linking``.
"""

from django.core.exceptions import ValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from api.exceptions import TelegramUnavailable
from api.permissions import IsCenterAdmin, IsCenterMember, IsOperationalCenter
from api.v1.serializers.telegram import TelegramLinkSerializer, TelegramStatusSerializer
from api.v1.views.mixins import CenterScopedMixin
from telegram_bot.client import TelegramClient, TelegramError
from telegram_bot.linking import create_group_link, disconnect_center


@extend_schema(tags=['telegram'], request=None, responses={201: TelegramLinkSerializer})
class TelegramConnectView(CenterScopedMixin, APIView):
    """A one-time link that adds the bot to a group and connects it to the center (center admins)."""

    permission_classes = [permissions.IsAuthenticated, IsCenterAdmin, IsOperationalCenter]

    def post(self, request, slug):
        client = TelegramClient()
        if not client.enabled:
            raise TelegramUnavailable
        try:
            url, expires_at = create_group_link(self.get_center(), request.user, client)
        except TelegramError:
            raise TelegramUnavailable from None
        except ValidationError as error:  # the permissions already checked the same rule
            raise PermissionDenied(' '.join(error.messages), code=error.code) from None
        return Response(TelegramLinkSerializer({'url': url, 'expires_at': expires_at}).data,
                        status=status.HTTP_201_CREATED)


@extend_schema(tags=['telegram'], request=None, responses=TelegramStatusSerializer)
class TelegramDisconnectView(CenterScopedMixin, APIView):
    """Disconnect the center's Telegram group; the bot leaves it (center admins)."""

    permission_classes = [permissions.IsAuthenticated, IsCenterAdmin, IsOperationalCenter]

    def post(self, request, slug):
        try:
            disconnect_center(self.get_center(), request.user)
        except ValidationError as error:  # the permissions already checked the same rule
            raise PermissionDenied(' '.join(error.messages), code=error.code) from None
        return Response(TelegramStatusSerializer(
            {'connected': False, 'me_linked': request.user.telegram_chat_id is not None}).data)


@extend_schema(tags=['telegram'], responses=TelegramStatusSerializer)
class TelegramStatusView(CenterScopedMixin, APIView):
    """Whether the center's group is connected and the caller linked (any member of an operational center)."""

    permission_classes = [permissions.IsAuthenticated, IsCenterMember, IsOperationalCenter]

    def get(self, request, slug):
        data = {'connected': self.get_center().telegram_chat_id is not None,
                'me_linked': request.user.telegram_chat_id is not None}
        return Response(TelegramStatusSerializer(data).data)
