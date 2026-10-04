"""
Abstract building blocks shared by concrete models.

* ``BaseModel``: creation and modification timestamps, newest-first ordering.
* ``CenterLinkedModel``: a mandatory link to the ``Center`` that owns the row,
  with a queryset that scopes rows to one center (see ADR 0005).
* ``CreatedByMixin``: an optional link to the user who created the row.

Concrete models that declare their own ``Meta`` must subclass
``BaseModel.Meta`` so they keep the default ordering. Django clears
``abstract`` on an inherited abstract ``Meta`` automatically.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class BaseModel(models.Model):
    """
    Abstract base for every concrete model: timestamps and default ordering.

    ``updated_at`` uses ``auto_now``, which Django only refreshes when the field
    is written. Callers that save with ``update_fields`` must include
    ``'updated_at'``, and ``QuerySet.update()`` must set it explicitly.
    """

    created_at = models.DateTimeField(_('created at'), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']


class CenterQuerySet(models.QuerySet):
    """Queryset for models owned by a center."""

    def for_center(self, center):
        """
        Return only the rows that belong to ``center``.

        Args:
            center: A saved ``Center`` instance or its primary key.

        Raises:
            ValueError: If ``center`` is ``None`` or an unsaved instance. An
                explicit error is safer than silently matching no rows, which
                would hide a missing scope in the caller.
        """
        center_id = getattr(center, 'pk', center)
        if center_id is None:
            raise ValueError('for_center() requires a saved Center or its primary key.')
        return self.filter(center_id=center_id)


class CenterLinkedModel(models.Model):
    """
    Abstract base for rows owned by exactly one center.

    The default manager is deliberately not scoped: it returns rows of every
    center. Code that serves a center must call ``for_center()`` explicitly
    (ADR 0005). Deleting a center deletes its rows (``CASCADE``).

    Reverse accessors are derived from the concrete model, for example
    ``center.core_membership_set`` and the lookup ``core_membership``.
    """

    center = models.ForeignKey(
        'core.Center',
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_set',
        related_query_name='%(app_label)s_%(class)s',
        verbose_name=_('center'),
    )

    objects = CenterQuerySet.as_manager()

    class Meta:
        abstract = True


class CreatedByMixin(models.Model):
    """
    Abstract mixin recording which user created a row.

    The link survives the user's deletion as ``NULL`` (``SET_NULL``) so that
    content is never lost with its author. ``related_name='+'`` adds no reverse
    accessor on the user, since many models will share this mixin.
    """

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name=_('created by'),
    )

    class Meta:
        abstract = True
