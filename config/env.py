"""
Typed readers for environment variables used by ``config.settings``.

Settings are configured exclusively through environment variables (optionally
loaded from a ``.env`` file at the repository root). These helpers centralise
the parsing rules so that every variable behaves the same way:

* An empty value is treated exactly like an unset variable. This keeps a
  half-filled ``.env`` (``KEY=``) from silently producing an empty secret or
  hostname, and lets a caller force the default by exporting an empty value.
* Missing required variables raise ``ImproperlyConfigured`` at import time,
  so a misconfigured process fails on startup instead of on first request.
"""

import os

from django.core.exceptions import ImproperlyConfigured


def _read(name):
    """Return the stripped value of ``name``, or ``None`` if unset or empty."""
    value = os.environ.get(name, '').strip()
    return value or None


def required(name):
    """
    Return the value of a required environment variable.

    Args:
        name: Name of the environment variable.

    Raises:
        ImproperlyConfigured: If the variable is unset or empty. The message
            names the variable and points to ``.env.example``.
    """
    value = _read(name)
    if value is None:
        raise ImproperlyConfigured(
            f'Required environment variable {name} is not set. '
            f'Copy .env.example to .env and set {name}.'
        )
    return value


def optional(name, default):
    """
    Return the value of an optional environment variable, or ``default``.

    Args:
        name: Name of the environment variable.
        default: Value returned when the variable is unset or empty.
    """
    value = _read(name)
    return default if value is None else value


def flag(name):
    """
    Return ``True`` only if the variable is exactly the string ``True``.

    The strict comparison is deliberate: values such as ``true``, ``1`` or
    ``yes`` are rejected so that a typo can never enable a dangerous setting
    like ``DEBUG`` in production.

    Args:
        name: Name of the environment variable.
    """
    return _read(name) == 'True'


def csv_list(name):
    """
    Return a comma-separated environment variable as a list of strings.

    Surrounding whitespace is stripped and empty items are dropped, so
    ``"a, b,,"`` yields ``['a', 'b']``. Unset or empty yields ``[]``.

    Args:
        name: Name of the environment variable.
    """
    value = _read(name)
    if value is None:
        return []
    return [item.strip() for item in value.split(',') if item.strip()]


def integer(name, default):
    """
    Return a non-negative integer environment variable, or ``default``.

    Args:
        name: Name of the environment variable.
        default: Value returned when the variable is unset or empty.

    Raises:
        ImproperlyConfigured: the value is not a non-negative integer, so a
        typo stops the process at startup instead of disabling a limit.
    """
    value = _read(name)
    if value is None:
        return default
    if not value.isdigit():
        raise ImproperlyConfigured(f'Environment variable {name} must be a non-negative integer, got {value!r}.')
    return int(value)
