"""Framework-policy checks. Release's Django job supplies the pinned dependency."""
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

ROOT = Path(__file__).resolve().parents[1]


def probe(code):
    pytest.importorskip('django', reason='Django framework checks run in the Release Django environment')
    prefix = '''
from django.conf import settings
from mariamem.django._database import Configuration
config = Configuration({})
settings.configure(INSTALLED_APPS=[], DATABASES={'default': {
    'ENGINE': 'django.db.backends.mysql', 'NAME': 'test_mariamem',
    'MARIAMEM_PREPARED': config}})
import django
django.setup()
'''
    result = subprocess.run([sys.executable, '-c', textwrap.dedent(prefix) + textwrap.dedent(code)],
                            cwd=ROOT, env=dict(os.environ, PYTHONPATH=str(ROOT / 'python')),
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
    assert result.returncode == 0, result.stdout


def test_reject_unsupported_case_options_and_ordinary_cases():
    probe('''
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase
from mariamem.django import PreparedTestCase, PreparedTransactionTestCase
from mariamem.django._cases import validate_case
for parent in (PreparedTestCase, PreparedTransactionTestCase):
    validate_case(parent)
    for options in ({'databases': {'other'}}, {'available_apps': []},
                    {'serialized_rollback': True}, {'reset_sequences': True},
                    {'tearDownClass': classmethod(lambda cls: None)}):
        cls = type('Unsupported', (parent,), options)
        try:
            validate_case(cls)
        except ImproperlyConfigured:
            pass
        else:
            raise AssertionError(options)
try:
    validate_case(TestCase)
except ImproperlyConfigured:
    pass
else:
    raise AssertionError('ordinary TestCase admitted')
''')


@pytest.mark.parametrize('options', [dict(parallel=2), dict(keepdb=True)])
def test_runner_rejects_retained_or_parallel_databases(options):
    probe('''
from django.core.exceptions import ImproperlyConfigured
from mariamem.django import PreparedDiscoverRunner
try:
    PreparedDiscoverRunner(**OPTIONS).run_tests([])
except ImproperlyConfigured:
    pass
else:
    raise AssertionError('unsupported runner admitted')
'''.replace('OPTIONS', repr(options)))


@pytest.mark.parametrize('option', ['reuse_db', 'nomigrations', 'numprocesses'])
def test_pytest_rejects_unsupported_mode_before_database_setup(option):
    probe('''
from types import SimpleNamespace
import pytest
from mariamem.django.pytest_plugin import pytest_configure
cleanups = []
cli = SimpleNamespace(add_cleanup=cleanups.append,
    getoption=lambda name, default=None: name == OPTION)
try:
    pytest_configure(cli)
except pytest.UsageError:
    pass
else:
    raise AssertionError('unsupported pytest admitted')
assert cleanups
for cleanup in cleanups:
    cleanup()
'''.replace('OPTION', repr(option)))


def test_runner_preserves_cleanup_that_django_would_suppress():
    probe('''
from types import SimpleNamespace
from django.test.runner import DiscoverRunner
from mariamem.django import _runner
primary, cleanup = ValueError('original run failure'), OSError('database cleanup')
def fail():
    raise cleanup
_runner.Manager = lambda config: SimpleNamespace(finish_databases=fail)
def run(self, *args, **kwargs):
    try:
        self.teardown_databases(None)
    except BaseException:
        pass  # Django suppresses this when run_suite already failed.
    raise primary
DiscoverRunner.run_tests = run
try:
    _runner.PreparedDiscoverRunner().run_tests([])
except BaseExceptionGroup as error:
    def flatten(e):
        if isinstance(e, BaseExceptionGroup):
            return [item for sub in e.exceptions for item in flatten(sub)]
        return [e]
    failures = flatten(error)
    assert primary in failures and cleanup in failures
else:
    raise AssertionError('failure disappeared')
''')


def test_runner_restores_test_environment_after_early_setup_failure():
    probe('''
from types import SimpleNamespace
from django.test.runner import DiscoverRunner
from mariamem.django import _runner
_runner.Manager = lambda config: SimpleNamespace()
def run(self, *args, **kwargs):
    self.setup_test_environment()
    raise ValueError('migration failure')
DiscoverRunner.run_tests = run
for _ in range(2):
    try:
        _runner.PreparedDiscoverRunner().run_tests([])
    except ValueError as error:
        assert str(error) == 'migration failure'
    else:
        raise AssertionError('failure disappeared')
''')


def test_release_uses_existing_django_job_and_installed_shared_wheel():
    workflow = (ROOT / '.github/workflows/django-lifecycle.yml').read_text()
    assert 'pip install --no-deps build/dist/*.whl' in workflow
    assert 'tests/django_prepared/run.py --installed' in workflow
    assert '--host-source-commit "$SOURCE_COMMIT"' in workflow
    assert 'tests/test_django_prepared_owners.py' in workflow


def test_nested_runner_does_not_close_existing_run():
    probe('''
from types import SimpleNamespace
from django.core.exceptions import ImproperlyConfigured
from mariamem.django import PreparedDiscoverRunner
calls = []
config.manager = SimpleNamespace(close=lambda: calls.append('BAD_CLOSE'))
try:
    PreparedDiscoverRunner().run_tests([])
except ImproperlyConfigured:
    pass
else:
    raise AssertionError('nested run admitted')
assert calls == []
''')


def test_no_database_suite_does_not_capture_uncreated_database():
    probe('''
from types import SimpleNamespace
from django.test.runner import DiscoverRunner
from mariamem.django import PreparedDiscoverRunner
prepared = []
runner = PreparedDiscoverRunner()
runner._mariamem_manager = SimpleNamespace(prepare=lambda: prepared.append(True))
DiscoverRunner.setup_databases = lambda *args, **kwargs: []
assert runner.setup_databases() == []
assert prepared == []
DiscoverRunner.setup_databases = lambda *args, **kwargs: [('configured',)]
assert runner.setup_databases() == [('configured',)]
assert prepared == [True]
''')
