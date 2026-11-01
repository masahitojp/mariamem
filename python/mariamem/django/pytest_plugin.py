"""Explicitly load with -p mariamem.django.pytest_plugin (plus pytest-django)."""
import pytest

from ._database import Manager, configuration


def _entry(config):
    entry = configuration(validate=False)
    if entry.manager is not None:
        raise pytest.UsageError('A mariamem prepared run is already active')
    if not getattr(config, '_mariamem_prepared_cleanup', False):
        config.add_cleanup(entry.close)
        config._mariamem_prepared_cleanup = True
    configuration()
    if (config.getoption('reuse_db', False) or config.getoption('nomigrations', False)
            or config.getoption('numprocesses', 0) or hasattr(config, 'workerinput')):
        raise pytest.UsageError('mariamem prepared tests require migrations and serial execution without --reuse-db')
    return entry


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    from django.conf import settings
    if settings.configured:
        _entry(config)


def pytest_collection_modifyitems(config, items):
    from django.test import TransactionTestCase
    from ._cases import validate_case
    _entry(config)
    for item in items:
        cls = getattr(item, 'cls', None)
        if cls is not None and issubclass(cls, TransactionTestCase):
            validate_case(cls)
        elif item.get_closest_marker('django_db') is not None or any(
                name in item.fixturenames for name in ('db', 'transactional_db', 'live_server')):
            raise pytest.UsageError('mariamem prepared entry currently supports only prepared Django classes')


@pytest.fixture(scope='session')
def django_db_modify_db_settings(django_db_modify_db_settings, django_db_blocker):
    # Runs before pytest-django's parent setup, including repeated pytest.main().
    with django_db_blocker.unblock():
        Manager(configuration())


@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    entry = configuration()
    # pytest-django already created/migrated the owned settings-time source.
    with django_db_blocker.unblock():
        manager = entry.manager
        manager.prepare()
    try:
        yield
    finally:
        with django_db_blocker.unblock():
            manager.finish_databases()
        # Parent fixture now drops its DB on the fresh teardown child. The
        # registered config cleanup closes that child after parent finalizers.
