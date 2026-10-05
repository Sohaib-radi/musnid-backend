"""Application configuration for the ``api`` app."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ApiConfig(AppConfig):
    """Registers the ``api`` app: versioned REST endpoints over the core models."""

    name = 'api'
    verbose_name = _('API')

    def ready(self):
        """Register the OpenAPI extensions (api/schema.py) with drf-spectacular."""
        from api import schema  # noqa: F401
