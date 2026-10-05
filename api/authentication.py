"""
Authentication for public endpoints that also recognise logged-in users.

``OptionalJWTAuthentication`` is SimpleJWT's authentication that never fails:
a valid access token identifies the user, anything else (no header, an
expired, malformed or blacklisted token, a deactivated account) leaves the
request anonymous. Public pages such as asking a question must not turn into a
401 because a browser still holds a stale token (ADR 0017, ADR 0019).
"""

from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication


class OptionalJWTAuthentication(JWTAuthentication):
    """JWT authentication that treats an unusable token as no token."""

    def authenticate(self, request):
        """Return ``(user, token)`` for a valid access token, otherwise ``None`` (anonymous)."""
        try:
            return super().authenticate(request)
        except exceptions.AuthenticationFailed:
            return None
