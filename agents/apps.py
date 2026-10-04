"""Application configuration for the ``agents`` app."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AgentsConfig(AppConfig):
    """Registers the ``agents`` app: the CrewAI flow that answers questions."""

    name = 'agents'
    verbose_name = _('Agents')
