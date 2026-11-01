"""Disposable D1 sketch using published mariamem0.6.0 and mysqlclient."""
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

from boot import source as sdk_source

class RealOwner:
    sequence = itertools.count()
    registry = []
    def __init__(self, owner):
        self.owner = owner
        self.closed = False
        self.label = 'owner-%d' % next(self.sequence)
        self.registry.append(self)
    def fork(self):
        if self.closed:
            raise RuntimeError('closed baseline')
        child = RealOwner(self.owner.fork())
        log('fork', owner=child.label)
        return child
    def snapshot(self):
        if self.closed:
            raise RuntimeError('consumed source')
        self.owner.wait_disconnected(timeout=5)
        baseline = RealOwner(self.owner.snapshot(timeout=30))
        self.closed = True
        log('capture', source=self.label, owner=baseline.label)
        return baseline
    def endpoint(self):
        return self.owner.connection_info()
    def close(self):
        if not self.closed:
            if hasattr(self.owner, 'wait_disconnected'):
                self.owner.wait_disconnected(timeout=5)
            self.owner.close()
            self.closed = True
            log('close', owner=self.label)

class Manager:
    def __init__(self):
        self.connection = connections['default']
        self.original = self.connection.settings_dict['NAME']
        self.debt = False
        self.cleanup_injected = False
        self.scopes = []
        self.teardown = None
        # Source is a real migrated Django test database, no user production DB.
        self.source = RealOwner(sdk_source)
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
        info = owner.endpoint()
        self.connection.settings_dict.update(HOST=info['host'], PORT=info['port'], USER=info['user'], PASSWORD=info['password'], NAME=self.original)
    def retire(self, owner):
        self.quiesce()
        if os.environ.get('D1_FAIL_CLEANUP') == '1' and not self.cleanup_injected:
            self.cleanup_injected = True
            log('close_failed', owner=owner.label, still_exists=not owner.closed)
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
            if self.teardown:
                info = self.teardown.endpoint()
                self.connection.settings_dict.update(HOST=info['host'], PORT=info['port'], USER=info['user'], PASSWORD=info['password'], NAME=self.original)
            else:
                self.connection.settings_dict['NAME'] = self.original
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
