"""
Admin for SimpleJWT's token blacklist, re-registered with Unfold.

SimpleJWT registers ``OutstandingToken`` and ``BlacklistedToken`` with Django's
plain ``ModelAdmin``; every admin in this project must use Unfold's
(ADR 0008), so they are unregistered and registered again with the same
behaviour. They appear in the sidebar's "Security" group.
"""

from django.contrib import admin
from rest_framework_simplejwt.token_blacklist import admin as jwt_admin
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from unfold.admin import ModelAdmin

admin.site.unregister(OutstandingToken)
admin.site.unregister(BlacklistedToken)


@admin.register(OutstandingToken)
class OutstandingTokenAdmin(jwt_admin.OutstandingTokenAdmin, ModelAdmin):
    """Refresh tokens issued to users (read-only, from SimpleJWT)."""


@admin.register(BlacklistedToken)
class BlacklistedTokenAdmin(jwt_admin.BlacklistedTokenAdmin, ModelAdmin):
    """Refresh tokens revoked by logout or rotation (from SimpleJWT)."""
