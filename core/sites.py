"""
The admin site: Django's admin is for platform administrators (superusers) only.

Users, specialists and center admins work in the frontend through the API.
``SuperuserAdminSite`` refuses every other account, even staff, on every admin
page; ``SuperuserAdminConfig`` installs it in place of Unfold's default site,
the way Unfold's own app config does.
"""

from django.apps import AppConfig
from django.contrib import admin
from django.contrib.admin import sites
from unfold.sites import UnfoldAdminSite


class SuperuserAdminSite(UnfoldAdminSite):
    """Unfold's admin site, open to active superusers only."""

    def __init__(self, name='admin'):
        super().__init__(name)
        # Imported here: this module loads with INSTALLED_APPS, before models are ready
        from core.forms import SuperuserAuthenticationForm

        self.login_form = SuperuserAuthenticationForm

    def has_permission(self, request):
        """Only an active superuser may use the admin; ``is_staff`` alone is not enough."""
        return request.user.is_active and request.user.is_superuser


class SuperuserAdminConfig(AppConfig):
    """Replaces ``unfold`` in ``INSTALLED_APPS``: same app, with ``SuperuserAdminSite`` as the admin site."""

    name = 'unfold'
    label = 'unfold'

    def ready(self):
        """Install the site before ``django.contrib.admin`` autodiscovers the admins (it comes later in the list)."""
        site = SuperuserAdminSite()
        admin.site = site
        sites.site = site
