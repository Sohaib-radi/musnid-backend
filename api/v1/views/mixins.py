"""Shared view behaviour for API v1."""

from django.shortcuts import get_object_or_404

from core.models import Center, Membership


class CenterScopedMixin:
    """
    For views under ``centers/<slug>/``: resolve the center among the caller's.

    Only centers where the caller has an active membership are visible, so a
    non-member gets 404 and cannot even learn that the slug exists. The center
    and the caller's membership are cached on the view for the permissions.
    """

    def get_center(self):
        """Return the caller's center for the URL slug, or raise 404."""
        if not hasattr(self, '_center'):
            visible = Center.objects.with_active_member(self.request.user)
            self._center = get_object_or_404(visible, slug=self.kwargs['slug'])
        return self._center

    def get_membership(self):
        """Return the caller's active membership of the center (or None)."""
        if not hasattr(self, '_membership'):
            self._membership = (
                Membership.objects.for_center(self.get_center()).active()
                .filter(user=self.request.user).first()
            )
        return self._membership
