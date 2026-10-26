"""Same business models/migrations as W4; exercise real Django test boundaries."""
import os
import MySQLdb
from django.db import IntegrityError, connection, transaction
from django.db.transaction import TransactionManagementError
from django.test import TestCase, TransactionTestCase
from orders.models import Order
from observation import record


def rows():
    return list(Order.objects.order_by('id').values_list('sku', 'quantity', 'status'))


def check_baseline(expected):
    with connection.cursor() as cursor:
        cursor.execute('SELECT DATABASE()')
        name = cursor.fetchone()[0]
        assert name == os.environ['W3_TEST_NAME'], name
        cursor.execute("SELECT name FROM django_migrations WHERE app='orders' ORDER BY name")
        assert cursor.fetchall() == (('0001_initial',), ('0002_status',))
    actual = rows()
    record('case_baseline', rows=actual, database=name, autocommit=connection.get_autocommit(), atomic=connection.in_atomic_block)
    assert actual == expected, actual


def committed_write():
    calls = []
    with transaction.atomic():
        Order.objects.create(sku='COMMIT', quantity=3)
        transaction.on_commit(lambda: calls.append('committed'))
    assert calls == ['committed']
    # A separate physical connection must see the committed mutation.
    config = connection.settings_dict
    observer = MySQLdb.connect(host=config['HOST'], port=int(config['PORT']),
                               user=config['USER'], passwd=config['PASSWORD'], db=config['NAME'])
    try:
        with observer.cursor() as cursor:
            cursor.execute("SELECT quantity FROM orders_order WHERE sku='COMMIT'")
            assert cursor.fetchone() == (3,)
    finally:
        observer.close()
    record('commit_observed', callbacks=calls, rows=rows())


class AtomicCases(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.shared = Order.objects.create(sku='CLASS', quantity=1)

    def setUp(self):
        check_baseline([('SEED', 2, 'ready'), ('CLASS', 1, 'ready')])

    def test_01_http_and_savepoint_recovery(self):
        response = self.client.post('/orders', {'sku': 'HTTP', 'quantity': 3})
        self.assertEqual(response.status_code, 302)
        with self.assertRaises(IntegrityError) as error:
            with transaction.atomic():
                Order.objects.create(sku='SEED')
        self.assertEqual(error.exception.args[0], 1062)
        self.assertEqual(Order.objects.get(sku='SEED').quantity, 2)
        with self.assertRaises(TransactionManagementError):
            transaction.commit()
        self.shared.status = 'changed'
        self.shared.save()
        record('atomic_recovery', errno=error.exception.args[0], rows=rows())

    def test_02_rollback_and_class_data(self):
        self.assertEqual(self.shared.status, 'ready')
        self.assertEqual(self.client.get('/orders').status_code, 200)
        self.assertFalse(Order.objects.filter(sku='HTTP').exists())


class SerializedCases(TransactionTestCase):
    serialized_rollback = True

    def setUp(self):
        check_baseline([('SEED', 2, 'ready')])

    def test_01_commit(self):
        committed_write()

    def test_02_seed_restored(self):
        committed_write()


class FlushCases(TransactionTestCase):
    def test_01_initial_seed(self):
        check_baseline([('SEED', 2, 'ready')])
        committed_write()

    def test_02_default_flush_is_empty(self):
        # Standard flush does not replay the application's data migration.
        check_baseline([])


class FailureCases(SerializedCases):
    def test_01_commit(self):
        committed_write()
        raise AssertionError('W3_EXPECTED_FAILURE_AFTER_COMMIT')
