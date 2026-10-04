"""
Per-IP throttles for anonymous asking (ADR 0017).

Only ``POST`` is counted: reading one's history costs nothing. The client IP is
taken by DRF's ``get_ident`` (``NUM_PROXIES``) and stored only as a keyed hash in
the cache key, so no IP address is written to the cache table in clear.
"""

from django.utils.crypto import salted_hmac
from rest_framework.throttling import SimpleRateThrottle


class AskRateThrottle(SimpleRateThrottle):
    """Base throttle for asking; subclasses set ``scope`` (rate in DEFAULT_THROTTLE_RATES)."""

    def allow_request(self, request, view):
        """Count and limit ``POST`` requests only."""
        if request.method != 'POST':
            return True
        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        """One counter per client IP and scope, keyed by a hash of the IP."""
        ident = salted_hmac('api.throttling.ask', self.get_ident(request)).hexdigest()
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class AskMinuteThrottle(AskRateThrottle):
    """Questions per minute from one IP."""

    scope = 'ask_minute'


class AskDayThrottle(AskRateThrottle):
    """Questions per day from one IP."""

    scope = 'ask_day'
