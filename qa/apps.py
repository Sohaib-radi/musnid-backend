"""Application configuration for the ``qa`` app."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class QaConfig(AppConfig):
    """Registers the ``qa`` app: questions, interactions and human labels."""

    name = 'qa'
    verbose_name = _('Questions and answers')
