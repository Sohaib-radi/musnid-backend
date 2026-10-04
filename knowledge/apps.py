"""Application configuration for the ``knowledge`` app."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class KnowledgeConfig(AppConfig):
    """Registers the ``knowledge`` app: source documents, chunks and search."""

    name = 'knowledge'
    verbose_name = _('Knowledge base')
