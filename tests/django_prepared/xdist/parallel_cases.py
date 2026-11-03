import os
import signal
import time
from django.db import connection
from orders.models import Order
import cases as original
from worker_settings import WORKER, MODE, OUT, barrier, event

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
    if not _seen_body:
        if MODE in ('crash','restart') and WORKER in ('gw0','gw1'):
            barrier('body')
        elif MODE not in ('prepare-failure','idle','crash','restart','cleanup-failure'):
            barrier('body')
        if MODE == 'restart' and WORKER == 'gw1':
            deadline = time.monotonic()+20
            while not (OUT/'replacement-ready').exists():
                if time.monotonic()>deadline:
                    raise TimeoutError('replacement worker did not prepare')
                time.sleep(.01)
    _seen_body = True
    event('body', database=expected, kind='atomic' if connection.in_atomic_block else 'transactional')
    if MODE in ('crash','restart') and WORKER == 'gw0':
        event('worker_kill', signal='SIGKILL')
        os.kill(os.getpid(), signal.SIGKILL)

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


class TestWithoutDatabase(original.NoDatabaseCase):
    pass
