"""Same authored SQL/ORM assertions for all worker counts; no artificial sleeps."""
import os
from django.db import connection
from orders.models import Order
import cases

def baseline():
    assert list(Order.objects.filter(sku='SEED').values_list('quantity', flat=True)) == [2]
    assert not Order.objects.filter(sku='COMMIT').exists()
    with connection.cursor() as cursor:
        cursor.execute('SELECT DATABASE()')
        worker = os.environ.get('PYTEST_XDIST_WORKER')
        expected = 'test_mariamem' + ('_' + worker if worker else '')
        assert cursor.fetchone() == (expected,)
        cursor.execute('SELECT n FROM prepared_sentinel')
        assert cursor.fetchall() == ((17,),)
        assert 'prepared_added' not in connection.introspection.table_names(cursor)
cases.baseline = baseline

# Eight classes allow loadscope to distribute real class work over four workers.
# Inherited first/second plus generated methods yield exactly SIZE per class.
size = int(os.environ['D1_TIMING_SIZE'])
for number in range(8):
    base = cases.AtomicCases if number % 2 == 0 else cases.TransactionalCases
    methods = {'test_%03d' % i: base.test_first if i % 2 else base.test_second
               for i in range(size - 2)}
    globals()['TestWorkload%02d' % number] = type('TestWorkload%02d' % number, (base,), methods)

# Do not expose the loop alias as an extra unittest class to pytest.
del base, methods, number, size
