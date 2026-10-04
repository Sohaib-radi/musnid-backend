"""Application configuration for the ``agents`` app."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AgentsConfig(AppConfig):
    """Registers the ``agents`` app: the CrewAI flow that answers questions."""

    name = 'agents'
    verbose_name = _('Agents')

    def ready(self):
        """
        Decline CrewAI's first-run trace prompt in every process.

        ``ready()`` runs in each process (gunicorn workers, management commands, tests)
        before any code imports CrewAI: nothing loaded during app setup imports
        ``agents.flow`` or ``agents.crews``. See ``agents.tracing``.
        """
        from agents.tracing import decline_crewai_traces

        decline_crewai_traces()
