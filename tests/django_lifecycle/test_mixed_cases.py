"""Mix Django unittest classes with pytest-django function fixtures/markers."""
import os
import pytest
if os.environ.get('W3_RUN') != '1':
    pytest.skip('bounded Django lifecycle owner is opt-in', allow_module_level=True)
from django.core.management import call_command
import cases
import mixed_cases


class TestAtomic(mixed_cases.AtomicCases):
    pass


class TestSerialized(mixed_cases.SerializedCases):
    pass


class TestFixture(mixed_cases.FixtureCases):
    pass


@pytest.fixture
def seeded_db(db):
    call_command('loaddata', 'orders_seed.json', verbosity=0)


@pytest.fixture
def seeded_transaction(transactional_db):
    call_command('loaddata', 'orders_seed.json', verbosity=0)


@pytest.mark.parametrize('index', [0, 1])
def test_plain_db(seeded_db, client, index):
    cases.check_baseline([('SEED', 2, 'ready')])
    assert client.post('/orders', {'sku': 'HTTP', 'quantity': 3}).status_code == 302


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
@pytest.mark.parametrize('index', [0, 1])
def test_serialized_function(index):
    cases.check_baseline([('SEED', 2, 'ready')])
    cases.committed_write()


@pytest.mark.parametrize('index', [0, 1])
def test_transaction_fixture(seeded_transaction, index):
    cases.check_baseline([('SEED', 2, 'ready')])
    cases.committed_write()
