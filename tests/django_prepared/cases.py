import os
import unittest
from django.db import connection, transaction
from mariamem.django import PreparedTestCase, PreparedTransactionTestCase
from orders.models import Order
from prepared_settings import event


def baseline():
    assert list(Order.objects.filter(sku='SEED').values_list('quantity', flat=True)) == [2]
    assert not Order.objects.filter(sku='COMMIT').exists()
    with connection.cursor() as cursor:
        cursor.execute('SELECT DATABASE()')
        assert cursor.fetchone() == ('test_mariamem',)
        cursor.execute('SELECT n FROM prepared_sentinel')
        assert cursor.fetchall() == ((17,),)
        assert 'prepared_added' not in connection.introspection.table_names(cursor)
    event('body')


class AtomicCases(PreparedTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Order.objects.create(sku='AFTER_SUPER')

    @classmethod
    def setUpTestData(cls):
        event('class-data')
        cls.order = Order.objects.create(sku='CLASS', quantity=7)
        cls.mutable = [1]
        transaction.on_commit(lambda: event('class-commit'))

    def test_first(self):
        baseline()
        assert self.order.quantity == 7
        assert self.mutable == [1]
        assert Order.objects.filter(sku='AFTER_SUPER').exists()
        self.order.quantity = 99
        self.order.save()
        self.mutable.append(2)

    def test_second(self):
        self.test_first()


class TransactionalCases(PreparedTransactionTestCase):
    def test_first(self):
        baseline()
        callbacks = []
        with transaction.atomic():
            Order.objects.create(sku='COMMIT')
            transaction.on_commit(lambda: callbacks.append(True))
        assert callbacks == [True]
        import MySQLdb
        cfg = connection.settings_dict
        observer = MySQLdb.connect(host=cfg['HOST'], port=int(cfg['PORT']), user=cfg['USER'],
                                   passwd=cfg['PASSWORD'], db=cfg['NAME'])
        try:
            with observer.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM orders_order WHERE sku='COMMIT'")
                assert cursor.fetchone() == (1,)
            event('commit-observed')
        finally:
            observer.close()
        with connection.cursor() as cursor:
            cursor.execute('UPDATE prepared_sentinel SET n=99')
            cursor.execute('CREATE TABLE prepared_added (n INT)')
        if os.environ.get('MARIAMEM_PREPARED_MODE') == 'body-failure':
            self.fail('PREPARED_BODY_FAILURE')

    def test_second(self):
        baseline()


class SetupFailure(PreparedTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        raise RuntimeError('PREPARED_CLASS_FAILURE')

    def test_refused(self):
        event('BAD_BODY')


class SetupSkip(PreparedTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        raise unittest.SkipTest('PREPARED_CLASS_SKIP')

    def test_refused(self):
        event('BAD_BODY')
