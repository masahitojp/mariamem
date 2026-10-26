"""Explicit test-only settings; ordinary Django/MySQL backend and lifecycle."""
import os
from settings import *  # noqa: F403

DATABASES['default']['TEST'] = {'NAME': os.environ['W3_TEST_NAME']}
TEST_RUNNER = 'observation.Runner'

FIXTURE_DIRS = [str(__import__('pathlib').Path(__file__).parent / 'fixtures')]
if os.environ.get('W3_BROKEN_MIGRATION') == '1':
    MIGRATION_MODULES = {'orders': 'failure_migrations'}
