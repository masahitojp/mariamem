import json, os
from django.db import connection
from django.test import TestCase, TransactionTestCase

def event(name):
    with open(os.environ['D1_EVENTS'], 'a') as stream:
        stream.write(json.dumps({'event': name, 'atomic': connection.in_atomic_block}) + '\n')

class Trace:
    @classmethod
    def setUpClass(cls):
        event(cls.__name__ + '.class.before')
        super().setUpClass()
        event(cls.__name__ + '.class.after')
    @classmethod
    def tearDownClass(cls):
        event(cls.__name__ + '.class_end.before')
        super().tearDownClass()
        event(cls.__name__ + '.class_end.after')
    @classmethod
    def _pre_setup(cls):
        event(cls.__name__ + '.pre.before')
        super()._pre_setup()
        event(cls.__name__ + '.pre.after')
    def _post_teardown(self):
        event(type(self).__name__ + '.post.before')
        super()._post_teardown()
        event(type(self).__name__ + '.post.after')

class Atomic(Trace, TestCase):
    @classmethod
    def setUpTestData(cls):
        event('Atomic.class_data')
    def test_01(self):
        event('Atomic.body.01')
        self.assertTrue(connection.in_atomic_block)
    def test_02(self):
        event('Atomic.body.02')
        self.assertTrue(connection.in_atomic_block)

class Transactional(Trace, TransactionTestCase):
    def test_01(self):
        event('Transactional.body.01')
        self.assertFalse(connection.in_atomic_block)
    def test_02(self):
        event('Transactional.body.02')
        self.assertFalse(connection.in_atomic_block)
