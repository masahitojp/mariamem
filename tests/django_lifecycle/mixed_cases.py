"""Mixed unittest classes use standard fixtures rather than class-order assumptions."""
from django.test import TransactionTestCase
import cases


class AtomicCases(cases.AtomicCases):
    fixtures = ['orders_seed.json']


class SerializedCases(cases.SerializedCases):
    pass


class FixtureCases(TransactionTestCase):
    fixtures = ['orders_seed.json']

    def setUp(self):
        cases.check_baseline([('SEED', 2, 'ready')])

    def test_01_commit(self):
        cases.committed_write()

    def test_02_commit_again(self):
        cases.committed_write()
