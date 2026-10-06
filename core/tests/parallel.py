"""
Worker setup for ``--parallel`` test runs.

This module must not import models, directly or indirectly. With the spawn
start method (the macOS default), each worker unpickles ``process_setup`` by
importing this module *before* ``django.setup()``; importing models at that
point raises ``AppRegistryNotReady``, the worker dies, and the pool respawns
it forever, which hangs the run.
"""

from django.conf import settings
from django.test.runner import ParallelTestSuite

TEST_PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']


def use_fast_password_hasher():
    """Replace ``PASSWORD_HASHERS`` with ``TEST_PASSWORD_HASHERS``."""
    settings.PASSWORD_HASHERS = TEST_PASSWORD_HASHERS


def disable_telegram():
    """
    Empty ``TELEGRAM_BOT_TOKEN`` and ``OPENAI_API_KEY``: values in .env must never let a
    test reach Telegram or OpenAI (tests pass fakes; translations are then skipped).
    """
    settings.TELEGRAM_BOT_TOKEN = ''
    settings.OPENAI_API_KEY = ''


class FastHasherParallelTestSuite(ParallelTestSuite):
    """Parallel suite whose spawned workers also use the fast password hasher and no Telegram token."""

    # Django calls this in each spawned worker, before django.setup(), as a
    # plain function (it passes ``process_setup.__func__``), hence no ``self``.
    def process_setup(*args):
        use_fast_password_hasher()
        disable_telegram()
