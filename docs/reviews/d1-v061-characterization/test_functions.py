import pytest
from django.db import connection
from test_trace import event

@pytest.mark.django_db
def test_atomic_function():
    event('function.atomic')
    assert connection.in_atomic_block

@pytest.mark.django_db(transaction=True)
def test_transactional_function():
    event('function.transactional')
    assert not connection.in_atomic_block
