"""
Error format of the API (ADR 0011).

Clients branch on codes, never on translated text:

* single-message errors are ``{"detail": <translated text>, "code": <code>}``;
* field validation errors keep DRF's ``{"<field>": [<messages>]}`` and add
  ``"codes": {"<field>": [<codes>]}``;
* a Django ``ValidationError`` raised by a core service becomes a 400 with its
  code (DRF would otherwise let it through as a 500).
"""

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions, status
from rest_framework.views import exception_handler as drf_exception_handler

from agents.replies import fixed_reply  # does not load CrewAI


class DailyCapacityReached(exceptions.APIException):
    """
    429 when the global daily limit of questions is reached (ADR 0017).

    The detail is the fixed "try again later" reply in the request language.
    """

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_code = 'daily_capacity'

    def __init__(self):
        super().__init__(fixed_reply('daily_capacity', get_language()))


class AskingUnavailable(exceptions.APIException):
    """503 when a question cannot be saved because no default center is configured."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_code = 'unavailable'
    default_detail = _('The service cannot take questions right now. Please try again later.')


class TelegramUnavailable(exceptions.APIException):
    """503 when the Telegram bot is off (no token) or Telegram cannot be reached (ADR 0023)."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_code = 'telegram_unavailable'
    default_detail = _('Telegram cannot be reached right now. Please try again in a moment.')


def exception_handler(exc, context):
    """DRF ``EXCEPTION_HANDLER``: see the module docstring for the format."""
    # Converted here rather than by DRF so that the code is added below.
    if isinstance(exc, DjangoValidationError):
        exc = _from_django(exc)
    elif isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()
    response = drf_exception_handler(exc, context)
    if response is None or not isinstance(exc, exceptions.APIException):
        return response
    codes = exc.get_codes()
    if isinstance(response.data, dict) and set(response.data) == {'detail'}:
        response.data['code'] = codes if isinstance(codes, str) else _first(codes)
    elif isinstance(response.data, dict):
        response.data['codes'] = codes
    return response


def _from_django(error):
    """Convert a Django ``ValidationError`` into DRF's, keeping message and code."""
    if hasattr(error, 'error_dict'):
        return exceptions.ValidationError({
            field: [exceptions.ErrorDetail(e.messages[0], e.code or 'invalid') for e in errors]
            for field, errors in error.error_dict.items()
        })
    messages = [exceptions.ErrorDetail(e.messages[0], e.code or 'invalid') for e in error.error_list]
    if len(messages) == 1:
        # Single message: reported as {"detail", "code"} like other single errors.
        return exceptions.ValidationError({'detail': messages[0]})
    return exceptions.ValidationError({'non_field_errors': messages})


def _first(codes):
    """Return the first code found in a nested codes structure."""
    if isinstance(codes, dict):
        return _first(next(iter(codes.values())))
    if isinstance(codes, list):
        return _first(codes[0])
    return codes
