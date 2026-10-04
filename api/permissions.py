"""
Permissions of the API. Each has a translated ``message`` and a stable
``code``, which DRF puts in the 403 response (``{"detail", "code"}``).

Center permissions read the center from the view's ``get_center()``
(``api.v1.views.mixins.CenterScopedMixin``), which already answers 404 to
non-members; these classes then decide 403 for members.
"""

from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import BasePermission

from core.models import Membership


class IsCenterMember(BasePermission):
    """The caller has an active membership of the center."""

    message = _('You are not a member of this center.')
    code = 'not_center_member'

    def has_permission(self, request, view):
        return view.get_membership() is not None


class IsCenterAdmin(BasePermission):
    """The caller is an active center admin of the center."""

    message = _('Only a center admin can do this.')
    code = 'not_center_admin'

    def has_permission(self, request, view):
        membership = view.get_membership()
        return membership is not None and membership.role == Membership.Role.CENTER_ADMIN


class IsOperationalCenter(BasePermission):
    """The center is approved and active."""

    message = _('This center is not operational: it is pending review, rejected or suspended.')
    code = 'center_not_operational'

    def has_permission(self, request, view):
        return view.get_center().is_operational
