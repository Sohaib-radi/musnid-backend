"""
Enumerations shared by several models.

``Language`` must list exactly the languages in ``settings.LANGUAGES``; a test
enforces it. The two cannot share one definition because settings are loaded
before models can be imported.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class Language(models.TextChoices):
    """Languages supported by the platform, as ISO 639-1 codes."""

    ARABIC = 'ar', _('Arabic')
    ENGLISH = 'en', _('English')
    FRENCH = 'fr', _('French')
