"""Extend the authored orders project's ordinary settings with a test DB name."""
import os
from pathlib import Path
from settings import *  # noqa: F403

DATABASES['default']['TEST'] = {'NAME': os.environ.get('E2E_TEST_DB_NAME', 'test_e2e_app')}
FIXTURE_DIRS = [str(Path(__file__).resolve().parents[3] / 'tests/django_lifecycle/fixtures')]
