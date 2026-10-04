"""Application configuration for the ``core`` app."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Registers the ``core`` app, which holds shared, project-wide code."""

    name = 'core'
