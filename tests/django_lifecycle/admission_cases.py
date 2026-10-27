"""These bodies must never execute when the migration fails."""
import os
from django.test import TestCase
from observation import record


class AdmissionCases(TestCase):
    def test_01_body(self):
        record('test_body_admitted', name='first')
        assert os.environ.get('W3_BROKEN_MIGRATION') != '1', 'W3_UNEXPECTED_TEST_ADMISSION'

    def test_02_body(self):
        record('test_body_admitted', name='second')
        assert os.environ.get('W3_BROKEN_MIGRATION') != '1', 'W3_UNEXPECTED_TEST_ADMISSION'
