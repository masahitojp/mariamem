"""Disposable D1 sketch. SQLite-copy ownership is NOT mariamem acceptance."""
import itertools
import os
from pathlib import Path
import shutil
import json
from django.db import connections
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.test.testcases import TestData
from django.test.runner import DiscoverRunner

manager = None

def log(event, **data):
    with open(os.environ['D1_EVENTS'], 'a') as stream:
        stream.write(json.dumps(dict(event=event, **data))+'\n')

class SQLiteCopy:
    """Backend stand-in: real file copies, source consumption, explicit close."""
    sequence = itertools.count()
    def __init__(self, path):
        self.path = Path(path)
        self.closed = False
    def fork(self):
        if self.closed:
            raise RuntimeError('closed baseline')
        path = self.path.parent / ('child-%d.sqlite' % next(self.sequence))
        shutil.copyfile(self.path, path)
        log('fork', path=str(path))
        return SQLiteCopy(path)
    def snapshot(self):
        if self.closed:
            raise RuntimeError('consumed source')
        path = self.path.with_name('baseline-%d.sqlite' % next(self.sequence))
        self.path.rename(path)
        self.closed = True
        log('capture', source=str(self.path), path=str(path))
        return SQLiteCopy(path)
    def close(self):
        if not self.closed:
            self.path.unlink(missing_ok=True)
            self.closed = True
            log('close', path=str(self.path))

class Manager:
    def __init__(self):
        self.connection = connections['default']
        self.original = self.connection.settings_dict['NAME']
        self.debt = False
        self.cleanup_injected = False
        self.scopes = []
        self.teardown = None
        # Source is a real migrated Django test database, no user production DB.
        self.source = SQLiteCopy(self.original)
        self.base = None
        try:
            with self.connection.cursor() as cur:
                cur.execute('CREATE TABLE d1_raw_sentinel (n INTEGER PRIMARY KEY)')
                cur.execute('INSERT INTO d1_raw_sentinel VALUES (17)')
            log('prepare')
            if os.environ.get('D1_FAIL_PREPARE') == '1':
                raise RuntimeError('D1_PREPARE_FAILURE')
            self.quiesce()
            self.base = self.source.snapshot()
        except BaseException:
            self.connection.close()
            self.source.close()
            raise
    def guard(self):
        if self.debt:
            raise RuntimeError('D1_CLEANUP_DEBT: next body refused')
    def quiesce(self):
        if self.connection.in_atomic_block:
            raise RuntimeError('D1_OPEN_ATOMIC: cannot switch owner')
        connections.close_all()
    def activate(self, owner):
        self.guard()
        self.quiesce()
        self.connection.settings_dict['NAME'] = str(owner.path)
    def retire(self, owner):
        self.quiesce()
        if os.environ.get('D1_FAIL_CLEANUP') == '1' and not self.cleanup_injected:
            self.cleanup_injected = True
            log('close_failed', path=str(owner.path), still_exists=owner.path.exists())
            raise RuntimeError('D1_INJECTED_CLEANUP_FAILURE')
        owner.close()
    def close(self):
        errors = []
        for scope in reversed(self.scopes):
            try:
                scope.close()
            except BaseException as error:
                errors.append(error)
        try:
            self.quiesce()
            if self.base:
                # Django still owns its final DB teardown: give it a fresh
                # disposable owner instead of a consumed preparation endpoint.
                self.teardown = self.base.fork()
                self.base.close()
        finally:
            self.connection.settings_dict['NAME'] = str(self.teardown.path) if self.teardown else self.original
        if errors:
            raise ExceptionGroup('D1 manager cleanup', errors)

class Scope:
    def __init__(self):
        manager.guard()
        self.source = manager.base.fork()
        self.base = self.child = None
        manager.scopes.append(self)
        manager.activate(self.source)
    def acquire(self):
        manager.guard()
        manager.quiesce()
        if self.child is not None and os.environ.get('D1_NO_RESTORE') == '1':
            manager.activate(self.child)
            return
        if self.base is None:
            if os.environ.get('D1_FAIL_CAPTURE') == '1':
                raise RuntimeError('D1_EXPECTED_CAPTURE_FAILURE')
            self.base = self.source.snapshot()
        self.child = self.base.fork()
        manager.activate(self.child)
    def release(self):
        if self.child and os.environ.get('D1_NO_RESTORE') == '1':
            manager.quiesce()
            return
        if self.child:
            try:
                manager.retire(self.child)
                self.child = None
            except BaseException:
                manager.debt = True
                raise
    def close(self):
        if self.child:
            manager.retire(self.child)
            self.child = None
        manager.retire(self.source)
        if self.base:
            manager.retire(self.base)

class PreparedMixin:
    """Opt-in: class setup is materialized, NOT a class-wide atomic."""
    @classmethod
    def setUpClass(cls):
        cls._d1_scope = Scope()
        cls.addClassCleanup(cls._d1_scope.close)
        # Deliberately bypass Django's class atomic and eager transaction setup.
        # All SimpleTestCase class guards/cleanups remain installed.
        SimpleTestCase.setUpClass.__func__(cls)
        if cls.databases != {'default'} or cls.available_apps is not None or cls.serialized_rollback:
            raise ValueError('prototype supports one alias, no available_apps/serialized rollback')
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
        # Test-local atomics have already exited; no cls_atomics to roll back.
        SimpleTestCase.tearDownClass.__func__(cls)
    @classmethod
    def _pre_setup(cls):
        cls._d1_scope.acquire()
        try:
            super()._pre_setup()
        except BaseException as original:
            try:
                cls._d1_scope.release()
            except BaseException as cleanup:
                raise BaseExceptionGroup('D1 setup and cleanup', [original, cleanup])
            raise
    def _post_teardown(self):
        try:
            super()._post_teardown()
        except BaseException as original:
            try:
                self._d1_scope.release()
            except BaseException as cleanup:
                raise BaseExceptionGroup('D1 teardown and cleanup', [original, cleanup])
            raise
        else:
            self._d1_scope.release()

class PreparedTestCase(PreparedMixin, TestCase):
    pass

class PreparedTransactionTestCase(PreparedMixin, TransactionTestCase):
    pass

class Runner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        global manager
        self.old_config = super().setup_databases(**kwargs)
        manager = Manager()
        return self.old_config
    def teardown_databases(self, old_config, **kwargs):
        try:
            if manager:
                manager.close()
        finally:
            try:
                super().teardown_databases(old_config, **kwargs)
            finally:
                if manager and manager.teardown:
                    manager.teardown.close()
