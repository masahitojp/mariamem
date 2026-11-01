import os
import unittest
from django.db import connection, transaction
from orders.models import Order
from entry import PreparedTestCase, PreparedTransactionTestCase, log


def baseline():
    with connection.cursor() as c:
        c.execute('SELECT DATABASE()')
        assert c.fetchone() == ('test_d1',)
        c.execute('SELECT n FROM d1_raw_sentinel')
        assert list(c.fetchall()) == [(17,)]
        c.execute("SELECT name FROM django_migrations WHERE app='orders' ORDER BY name")
        assert list(c.fetchall()) == [('0001_initial',), ('0002_status',)]
    assert list(Order.objects.filter(sku='SEED').values_list('quantity', flat=True)) == [2]
    assert not Order.objects.filter(sku='COMMIT').exists()
    log('body', atomic=connection.in_atomic_block)

class AtomicCases(PreparedTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Order.objects.create(sku='AFTER_SUPER', quantity=5)
    @classmethod
    def setUpTestData(cls):
        log('setUpTestData')
        cls.shared = Order.objects.create(sku='CLASS', quantity=1)
    def test_01(self):
        baseline()
        assert Order.objects.filter(sku='AFTER_SUPER').exists()
        self.shared.quantity = 999
        self.shared.save()
    def test_02(self):
        baseline()
        assert self.shared.quantity == 1
        assert Order.objects.get(sku='CLASS').quantity == 1
        assert Order.objects.filter(sku='AFTER_SUPER').exists()

class TransactionalCases(PreparedTransactionTestCase):
    def test_01(self):
        baseline()
        callbacks = []
        with transaction.atomic():
            Order.objects.create(sku='COMMIT')
            transaction.on_commit(lambda: callbacks.append('committed'))
        assert callbacks == ['committed']
        import MySQLdb
        cfg = connection.settings_dict
        observer = MySQLdb.connect(host=cfg['HOST'], port=int(cfg['PORT']), user=cfg['USER'], passwd=cfg['PASSWORD'], db=cfg['NAME'])
        try:
            with observer.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM orders_order WHERE sku='COMMIT'")
                assert cur.fetchone() == (1,)
            log('independent_commit_observed')
        finally:
            observer.close()
        with connection.cursor() as cur:
            cur.execute('UPDATE d1_raw_sentinel SET n=99')
            cur.execute('CREATE TABLE d1_added (n INT)')
        if os.environ.get('D1_EXPECT_FAILURE') == '1':
            self.fail('D1_EXPECTED_FAILURE_AFTER_COMMIT')
    def test_02(self):
        baseline()
        with connection.cursor() as cur:
            assert 'd1_added' not in connection.introspection.table_names(cur)

class SetupFailure(PreparedTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        raise RuntimeError('D1_EXPECTED_CLASS_SETUP_FAILURE')
    def test_not_admitted(self):
        log('BAD_BODY')

class SetupSkip(PreparedTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        raise unittest.SkipTest('D1_EXPECTED_CLASS_SETUP_SKIP')
    def test_not_admitted(self):
        log('BAD_BODY')
