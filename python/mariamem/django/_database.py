"""Declarative test settings and database-setup-time ownership."""
import atexit
import re
from copy import deepcopy

from ._lifecycle import Owners, preserving_cleanup


KEY = 'MARIAMEM_PREPARED'


class Configuration:
    def __init__(self, options, *, max_forks=None, fork_timeout=30):
        self.options = deepcopy(options)
        self.max_forks, self.fork_timeout = max_forks, fork_timeout
        self.source = None
        self.manager = None

    def __deepcopy__(self, memo):
        # Django/pytest may copy settings; ownership must never be duplicated.
        return self

    def start(self):
        if self.source is None:
            from mariamem import start
            self.source = start(**self.options)
            atexit.register(self.close)
        return self.source

    def close(self):
        def close_source():
            if self.source is not None:
                self.source.close()
        with preserving_cleanup(close_source):
            if self.manager is not None:
                self.manager.close()
        self.source = self.manager = None
        atexit.unregister(self.close)


def prepared_database(*, test_name='test_mariamem', options=None,
                      max_forks=None, fork_timeout=30):
    """Declare a prepared default database; do not acquire a host.

    The runner/plugin starts it immediately before Django database setup.
    SQL outside that lifecycle is rejected by the guarded MySQL backend.
    """
    if not isinstance(test_name, str) or not re.fullmatch(r'test_[A-Za-z0-9_]+', test_name):
        raise ValueError('test_name must start with test_ and contain only letters, digits or underscores')
    from mariamem._forklimit import capacity, wait_nanoseconds
    capacity(max_forks)
    wait_nanoseconds(fork_timeout, allow_none=False)
    config = Configuration(options or {}, max_forks=max_forks, fork_timeout=fork_timeout)
    return dict(ENGINE='mariamem.django.backend', NAME='mariamem_prepare',
                HOST='', PORT='', USER='', PASSWORD='',
                TEST={'NAME': test_name}, CONN_MAX_AGE=0, **{KEY: config})


def configuration(*, validate=True):
    from django.conf import settings
    from django.core.exceptions import ImproperlyConfigured
    database = settings.DATABASES.get('default', {})
    config = database.get(KEY)
    if not isinstance(config, Configuration):
        raise ImproperlyConfigured('Use prepared_database() in dedicated test settings')
    if validate:
        if set(settings.DATABASES) != {'default'}:
            raise ImproperlyConfigured('mariamem prepared tests require only the default database alias')
        if (database.get('ENGINE') != 'mariamem.django.backend'
                or database.get('TEST', {}).get('MIRROR')
                or not database.get('TEST', {}).get('MIGRATE', True)):
            raise ImproperlyConfigured('Prepared entry requires its guarded MySQL backend, migrations and no test mirror')
        from mariamem import routing
        if routing._active is not None:
            raise ImproperlyConfigured('Prepared Django and routing/shadow_maria cannot share a run')
    return config


class Manager:
    def __init__(self, config):
        from django.db import connections
        from django.core.exceptions import ImproperlyConfigured
        if config.manager is not None:
            raise ImproperlyConfigured('A mariamem prepared run is already active')
        self.config = config
        self.connection = connections['default']
        self.original = self.connection.settings_dict.copy()
        self.owners = Owners(max_forks=config.max_forks, fork_timeout=config.fork_timeout)
        self.source = self.owners.own(config.start())
        self.base = self.teardown = None
        self.finished = False
        config.manager = self
        self.activate(self.source, name='mariamem_prepare')

    def quiesce(self):
        from django.db import connections
        if self.connection.in_atomic_block:
            raise RuntimeError('Cannot switch mariamem database inside an atomic block')
        connections.close_all()

    def activate(self, database, *, name=None):
        self.quiesce()
        info = database.connection_info()
        self.connection.settings_dict.update(HOST=info['host'], PORT=info['port'],
                                             USER=info['user'], PASSWORD=info['password'])
        if name is not None:
            self.connection.settings_dict['NAME'] = name

    def prepare(self):
        from django.conf import settings
        callback = getattr(settings, 'MARIAMEM_DJANGO_PREPARE', None)
        if isinstance(callback, str):
            from django.utils.module_loading import import_string
            callback = import_string(callback)
        if callback is not None:
            if not callable(callback):
                raise TypeError('MARIAMEM_DJANGO_PREPARE must be a callable or dotted path')
            callback(self.connection)
        self.quiesce()
        self.base = self.owners.capture(self.source)

    def finish_databases(self):
        """Give Django a fresh disposable child for its own final DROP DATABASE."""
        if self.finished:
            return
        self.finished = True
        with preserving_cleanup(lambda: self.owners.close(keep=self.teardown)):
            self.quiesce()
            if self.base is not None:
                # Retire remaining class/test owners before taking R's last
                # slot. A failed retirement aborts DROP and still runs cleanup.
                self.owners.close(keep=self.base)
                # Finalization may bypass the test latch, never the SDK cap.
                self.teardown = self.owners.own(self.base.fork(timeout=self.config.fork_timeout))
                self.activate(self.teardown)

    def close(self):
        def close_owners():
            self.owners.close()
        try:
            with preserving_cleanup(close_owners):
                self.quiesce()
        finally:
            self.connection.settings_dict.clear()
            self.connection.settings_dict.update(self.original)


class Scope:
    def __init__(self, manager):
        self.manager = manager
        self.base = self.child = None
        manager.owners.guard()
        self.source = manager.owners.fork(manager.base)
        manager.activate(self.source)

    def acquire(self):
        m = self.manager
        m.owners.guard()
        m.quiesce()
        if self.base is None:
            self.base = m.owners.capture(self.source)
        self.child = m.owners.fork(self.base)
        m.activate(self.child)

    def release(self):
        m = self.manager
        try:
            m.quiesce()
            if self.child is not None:
                self.child.wait_disconnected(timeout=5)
                m.owners.retire(self.child)
                self.child = None
        except BaseException:
            m.owners.debt = True
            raise

    def close(self):
        def close_baselines():
            errors = []
            for owner in (self.base, self.source):
                if owner is not None:
                    try:
                        self.manager.owners.retire(owner)
                    except BaseException as error:
                        errors.append(error)
            if errors:
                raise BaseExceptionGroup('mariamem class cleanup failed', errors)
        with preserving_cleanup(close_baselines):
            self.release()
