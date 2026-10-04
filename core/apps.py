"""Application configuration for the ``core`` app."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Registers the ``core`` app, which holds shared, project-wide code."""

    name = 'core'
    # Shown as the admin breadcrumb and app heading. A brand name, so it is
    # deliberately not translated (ADR 0009).
    verbose_name = 'Musnid'
