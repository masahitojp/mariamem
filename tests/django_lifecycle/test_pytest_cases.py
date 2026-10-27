"""Explicit pytest-django fixtures/markers; no DB-setup override or routing."""
import os
import pytest
if os.environ.get("W3_RUN") != "1":
    pytest.skip("bounded Django lifecycle owner is opt-in", allow_module_level=True)
from cases import check_baseline, committed_write
from django.db import IntegrityError, transaction
from orders.models import Order
from observation import record

MODE = os.environ['W3_MODE']


@pytest.mark.parametrize('index', [0, 1])
def test_atomic(db, client, index):
    if MODE != 'atomic':
        pytest.fail('wrong selection: atomic')
    check_baseline([('SEED', 2, 'ready')])
    assert client.post('/orders', {'sku': 'HTTP', 'quantity': 3}).status_code == 302
    with pytest.raises(IntegrityError) as error:
        with transaction.atomic():
            Order.objects.create(sku='SEED')
    assert error.value.args[0] == 1062
    assert Order.objects.get(sku='SEED').quantity == 2
    record('atomic_recovery', errno=error.value.args[0])


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
@pytest.mark.parametrize('index', [0, 1])
def test_serialized(index):
    check_baseline([('SEED', 2, 'ready')])
    committed_write()
    if MODE == 'failure' and index == 0:
        raise AssertionError('W3_EXPECTED_FAILURE_AFTER_COMMIT')


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize('index', [0, 1])
def test_flush(index):
    check_baseline([('SEED', 2, 'ready')] if index == 0 else [])
    if index == 0:
        committed_write()
