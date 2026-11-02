from django.db import connection
from orders.models import Order
import cases as original
from spike_settings import WORKER, MODE, barrier, event

_seen_body = False

def baseline():
    global _seen_body
    expected = 'test_mariamem_' + WORKER
    with connection.cursor() as cursor:
        cursor.execute('SELECT DATABASE()')
        assert cursor.fetchone() == (expected,)
        cursor.execute('SELECT worker FROM worker_seed')
        assert cursor.fetchall() == ((WORKER,),)
        cursor.execute('SELECT n FROM prepared_sentinel')
        assert cursor.fetchall() == ((17,),)
        assert 'prepared_added' not in connection.introspection.table_names(cursor)
    assert list(Order.objects.filter(sku='SEED').values_list('quantity', flat=True)) == [2]
    assert not Order.objects.filter(sku='COMMIT').exists()
    if not _seen_body and MODE != 'prepare-failure':
        barrier('body')
    _seen_body = True
    event('body', database=expected, kind='atomic' if connection.in_atomic_block else 'transactional')

original.baseline = baseline

class TestAtomic(original.AtomicCases):
    test_03 = original.AtomicCases.test_first
    test_04 = original.AtomicCases.test_second
    test_05 = original.AtomicCases.test_first
    test_06 = original.AtomicCases.test_second

class TestTransactional(original.TransactionalCases):
    test_03 = original.TransactionalCases.test_first
    test_04 = original.TransactionalCases.test_second
    test_05 = original.TransactionalCases.test_first
    test_06 = original.TransactionalCases.test_second
