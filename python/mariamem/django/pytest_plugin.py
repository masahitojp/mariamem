"""Explicitly load with -p mariamem.django.pytest_plugin (plus pytest-django)."""
import pytest

from ._database import Manager, configuration
from . import _xdist


def _entry(config):
    entry = configuration(validate=False)
    if entry.manager is not None:
        raise pytest.UsageError('A mariamem prepared run is already active')
    if not getattr(config, '_mariamem_prepared_cleanup', False):
        config.add_cleanup(entry.close)
        config._mariamem_prepared_cleanup = True
    from mariamem import routing
    if routing._active is not None:
        raise pytest.UsageError('Prepared Django and routing/shadow_maria cannot share a run')
    configuration()
    if config.getoption('reuse_db', False) or config.getoption('nomigrations', False):
        raise pytest.UsageError('mariamem prepared tests require migrations without --reuse-db')
    _xdist.validate(config)
    return entry


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_cmdline_main(config):
    # Observe the symbolic request before xdist resolves it to a CPU count.
    if config.getoption('tx', []) or config.getoption('looponfail', False):
        raise pytest.UsageError('Prepared Django supports explicit -n N, not manual --tx or loop-on-fail')
    if config.getoption('numprocesses', None) in ('auto', 'logical'):
        raise pytest.UsageError('Prepared Django workers require explicit -n N; auto/logical are unsupported')
    yield


@pytest.hookimpl(optionalhook=True)
def pytest_xdist_setupnodes(config, specs):
    _xdist.validate(config)
    _xdist.local_specs(specs)


@pytest.hookimpl(optionalhook=True)
def pytest_configure_node(node):
    _xdist.local_specs([node.gateway.spec])
    node.workerinput[_xdist.KEY] = 1


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    from django.conf import settings
    if settings.configured:
        _entry(config)


def pytest_collection_modifyitems(config, items):
    from django.test import SimpleTestCase
    from django.core.exceptions import ImproperlyConfigured
    from ._cases import validate_case
    _entry(config)
    for item in items:
        if (item.get_closest_marker('shadow_maria') is not None
                or 'mariamem_app_db' in item.fixturenames):
            raise pytest.UsageError('Prepared Django and shadow_maria/mariamem_app_db cannot share a run; choose one lifecycle')
        cls = getattr(item, 'cls', None)
        if cls is not None and issubclass(cls, SimpleTestCase) and cls.databases:
            try:
                validate_case(cls)
            except ImproperlyConfigured as error:
                raise pytest.UsageError(str(error)) from error
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
    # pytest-django already created/migrated the source acquired at database setup.
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
