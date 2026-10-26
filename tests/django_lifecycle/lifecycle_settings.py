"""Explicit test-only settings; ordinary Django/MySQL backend and lifecycle."""
import os
from settings import *  # noqa: F403

DATABASES['default']['TEST'] = {'NAME': os.environ['W3_TEST_NAME']}
TEST_RUNNER = 'observation.Runner'
