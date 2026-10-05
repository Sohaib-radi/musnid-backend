"""Telegram connection of a center (ADR 0023): the one-time link and the status the dashboard polls."""

from rest_framework import serializers


class TelegramLinkSerializer(serializers.Serializer):
    """A one-time Telegram link; open it in a new tab (or show it as a QR code)."""

    url = serializers.URLField(help_text='t.me link: startgroup (adds the bot to a group) or start (private chat).')
    expires_at = serializers.DateTimeField(help_text='The link stops working after this time (10 minutes).')


class MyTelegramSerializer(serializers.Serializer):
    """Whether the caller's Telegram account is linked."""

    telegram_linked = serializers.BooleanField(help_text="The caller's Telegram account is linked.")


class TelegramStatusSerializer(serializers.Serializer):
    """Whether the center's group is connected and the caller's account linked; polled while connecting."""

    connected = serializers.BooleanField(help_text='The center has a Telegram group connected through the bot.')
    me_linked = serializers.BooleanField(help_text="The caller's Telegram account is linked.")
