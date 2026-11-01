"""Opt-in cases: materialized class setup, independent per-test Forks."""
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.test.testcases import TestData

from ._database import Scope, configuration
from ._lifecycle import preserving_cleanup


def validate_case(cls):
    if not issubclass(cls, _PreparedMixin):
        raise ImproperlyConfigured('Use PreparedTestCase or PreparedTransactionTestCase for every database test')
    if (cls.databases != {'default'} or cls.available_apps is not None
            or cls.serialized_rollback or cls.reset_sequences):
        raise ImproperlyConfigured('Prepared cases require default only, without available_apps, serialized_rollback or reset_sequences')
    if cls.tearDownClass.__func__ is not _PreparedMixin.tearDownClass.__func__:
        raise ImproperlyConfigured('Prepared cases do not yet support custom tearDownClass; use addClassCleanup for non-database resources')


class _PreparedMixin:
    @classmethod
    def setUpClass(cls):
        validate_case(cls)
        manager = configuration().manager
        if manager is None or manager.base is None:
            raise ImproperlyConfigured('Use PreparedDiscoverRunner or mariamem.django.pytest_plugin')
        # Scope construction may fail after acquisition; Manager retains handles.
        cls._mariamem_scope = Scope(manager)
        cls.addClassCleanup(cls._mariamem_scope.close)
        SimpleTestCase.setUpClass.__func__(cls)
        if issubclass(cls, TestCase):
            if cls.fixtures:
                call_command('loaddata', *cls.fixtures, verbosity=0, database='default')
            before = cls.__dict__.copy()
            cls.setUpTestData()
            for name, value in list(cls.__dict__.items()):
                if value is not before.get(name):
                    setattr(cls, name, TestData(name, value))

    @classmethod
    def tearDownClass(cls):
        SimpleTestCase.tearDownClass.__func__(cls)

    @classmethod
    def _pre_setup(cls):
        try:
            cls._mariamem_scope.acquire()
            super()._pre_setup()
        except BaseException:
            with preserving_cleanup(cls._mariamem_scope.release):
                raise

    def _post_teardown(self):
        with preserving_cleanup(self._mariamem_scope.release):
            super()._post_teardown()


class PreparedTestCase(_PreparedMixin, TestCase):
    """Per-test Django atomic; committed class setup captured once before tests.

    Unlike Django TestCase, class setup has no enclosing atomic block. Fixtures
    and setUpTestData execute once in autocommit; on_commit may execute there.
    """


class PreparedTransactionTestCase(_PreparedMixin, TransactionTestCase):
    """Allow commits; every test starts from the captured class schema/seed."""
