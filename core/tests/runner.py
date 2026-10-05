"""
Project test runner.

It does two things on top of Django's ``DiscoverRunner``:

1. Creates the tables of test-only models (see below).
2. Uses a fast password hasher. The production hasher (PBKDF2) is deliberately
   slow; measured on the development machine it made a few login tests take
   over a second each. Django's documentation recommends a faster hasher for
   tests. It is applied in the main process and in every ``--parallel``
   worker (see ``core.tests.parallel``).

Test-only tables

Test-only models (``core.tests.support.TEST_ONLY_MODELS``) have no migration,
so ``migrate`` does not create their tables. This runner creates them from a
``post_migrate`` handler, which fires while Django builds the test database:

* after migrations and before the database is cloned, so ``--parallel``
  workers inherit the tables from the clone;
* also with ``--keepdb``, where ``migrate`` still runs on the kept database;
  tables that already exist are skipped.

The handler is connected only for the duration of ``setup_databases``, so a
normal ``migrate`` never sees it.
"""

from django.apps import apps
from django.db import connections
from django.db.models.signals import post_migrate
from django.test.runner import DiscoverRunner

from core.tests.parallel import FastHasherParallelTestSuite, disable_telegram, use_fast_password_hasher
from core.tests.support import TEST_ONLY_MODELS

_DISPATCH_UID = 'core.tests.runner.create_test_only_tables'


def create_test_only_tables(using, **kwargs):
    """
    Create the table of every test-only model that does not exist yet.

    Args:
        using: Alias of the database that was just migrated.
    """
    connection = connections[using]
    existing = set(connection.introspection.table_names())
    with connection.schema_editor() as editor:
        for model in TEST_ONLY_MODELS:
            if model._meta.db_table not in existing:
                editor.create_model(model)


class TestRunner(DiscoverRunner):
    """``DiscoverRunner`` with test-only tables and a fast password hasher."""

    parallel_test_suite = FastHasherParallelTestSuite

    def setup_test_environment(self, **kwargs):
        """Set up Django's test environment, then switch to the fast hasher and turn the Telegram bot off."""
        super().setup_test_environment(**kwargs)
        use_fast_password_hasher()
        disable_telegram()

    def setup_databases(self, **kwargs):
        """Build the test databases with test-only tables (see module docstring)."""
        # Sent once per app; reacting to core alone runs the handler once, and
        # core is migrated by then, which the test models' foreign keys need.
        sender = apps.get_app_config('core')
        post_migrate.connect(create_test_only_tables, sender=sender, dispatch_uid=_DISPATCH_UID)
        try:
            return super().setup_databases(**kwargs)
        finally:
            post_migrate.disconnect(sender=sender, dispatch_uid=_DISPATCH_UID)
