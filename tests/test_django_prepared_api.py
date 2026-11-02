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
    'ENGINE': 'mariamem.django.backend', 'NAME': 'test_mariamem',
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


@pytest.mark.parametrize('option', ['reuse_db', 'nomigrations'])
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
    self._mariamem_manager = SimpleNamespace(finish_databases=fail)
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
    assert 'tests/django_prepared/xdist/run.py --installed' in workflow
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


def test_no_database_suite_does_not_start_or_capture():
    probe('''
from types import SimpleNamespace
from django.test.runner import DiscoverRunner
from mariamem.django import _runner
started, prepared = [], []
def manager(config):
    started.append(True)
    return SimpleNamespace(prepare=lambda: prepared.append(True))
_runner.Manager = manager
runner = _runner.PreparedDiscoverRunner()
runner._mariamem_manager = None
DiscoverRunner.setup_databases = lambda *args, **kwargs: []
assert runner.setup_databases(aliases={}) == []
assert started == prepared == []
DiscoverRunner.setup_databases = lambda *args, **kwargs: [('configured',)]
assert runner.setup_databases(aliases={'default'}) == [('configured',)]
assert started == prepared == [True]
''')


def test_settings_check_and_shell_never_acquire_host():
    probe('''
import mariamem
from mariamem.django import prepared_database
from django.core.management import call_command
calls = []
def forbidden(**options):
    calls.append(True)
    raise AssertionError('host started outside database setup')
mariamem.start = forbidden
settings.DATABASES['default'] = prepared_database()
assert settings.DATABASES['default']['MARIAMEM_PREPARED'].source is None
call_command('check', verbosity=0)
call_command('shell', command='pass', verbosity=0)
assert calls == []
''')


def test_database_access_before_setup_refuses_before_driver_connect():
    probe('''
import mariamem
import MySQLdb
from django.db import connection
from django.core.exceptions import ImproperlyConfigured
mariamem.start = lambda **kw: (_ for _ in ()).throw(AssertionError('unexpected start'))
MySQLdb.connect = lambda **kw: (_ for _ in ()).throw(AssertionError('unexpected driver dial'))
try:
    connection.cursor()
except ImproperlyConfigured as error:
    assert 'not active' in str(error)
else:
    raise AssertionError('SQL admitted before setup')
''')


@pytest.mark.parametrize('fixture_names', [[], ['mariamem_app_db']])
def test_prepared_collection_rejects_shadow_marker_or_routing_fixture(fixture_names):
    probe('''
from types import SimpleNamespace
import pytest
import mariamem
from mariamem.django import PreparedTestCase
from mariamem.django.pytest_plugin import pytest_collection_modifyitems
mariamem.start = lambda **kw: (_ for _ in ()).throw(AssertionError('unexpected start'))
cli = SimpleNamespace(add_cleanup=lambda close: None, getoption=lambda name, default=None: default)
item = SimpleNamespace(cls=PreparedTestCase, fixturenames=FIXTURES,
    get_closest_marker=lambda name: object() if name == 'shadow_maria' and not FIXTURES else None)
try:
    pytest_collection_modifyitems(cli, [item])
except pytest.UsageError as error:
    assert 'cannot share a run' in str(error)
else:
    raise AssertionError('mixed lifecycle admitted')
assert config.source is None and config.manager is None
'''.replace('FIXTURES', repr(fixture_names)))


def test_active_routing_registry_is_rejected_before_start():
    probe('''
import mariamem
from mariamem import routing
from django.core.exceptions import ImproperlyConfigured
from mariamem.django._database import configuration
mariamem.start = lambda **kw: (_ for _ in ()).throw(AssertionError('unexpected start'))
routing._active = object()
try:
    configuration()
except ImproperlyConfigured as error:
    assert 'cannot share a run' in str(error)
else:
    raise AssertionError('routing registry admitted')
assert config.source is None
''')


def test_discovery_error_happens_without_starting_host():
    probe('''
import mariamem
from django.test.runner import DiscoverRunner
from mariamem.django import PreparedDiscoverRunner
mariamem.start = lambda **kw: (_ for _ in ()).throw(AssertionError('unexpected start'))
def fail(self, *args, **kwargs):
    raise ValueError('collection failed')
DiscoverRunner.build_suite = fail
try:
    PreparedDiscoverRunner().run_tests([])
except ValueError as error:
    assert str(error) == 'collection failed'
else:
    raise AssertionError('discovery error lost')
assert config.source is None and config.manager is None
''')


@pytest.mark.parametrize('placement', ['function', 'class', 'module'])
def test_real_pytest_rejects_inherited_shadow_marks_without_start(tmp_path, placement):
    text = 'import pytest\nfrom mariamem.django import PreparedTestCase\n'
    if placement == 'module':
        text += 'pytestmark = pytest.mark.shadow_maria\n'
    if placement == 'class':
        text += '@pytest.mark.shadow_maria\n'
    text += 'class TestShadow(PreparedTestCase):\n'
    if placement == 'function':
        text += '    @pytest.mark.shadow_maria\n'
    text += '    def test_never(self):\n        raise AssertionError("body admitted")\n'
    test_file = tmp_path / 'test_shadow.py'
    test_file.write_text(text)
    probe('''
import mariamem, os, pytest
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
mariamem.start = lambda **kw: (_ for _ in ()).throw(AssertionError('unexpected start'))
result = pytest.main(['-p','pytest_django.plugin','-p','mariamem.django.pytest_plugin',
                      TEST_FILE,'--collect-only','-q'])
assert result == pytest.ExitCode.USAGE_ERROR
assert config.source is None and config.manager is None
'''.replace('TEST_FILE', repr(str(test_file))))


def test_real_pytest_collection_only_never_starts_host(tmp_path):
    test_file = tmp_path / 'test_collect.py'
    test_file.write_text('from mariamem.django import PreparedTestCase\n'
                         'class TestCollect(PreparedTestCase):\n'
                         '    def test_never(self):\n        pass\n')
    probe('''
import mariamem, os, pytest
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
mariamem.start = lambda **kw: (_ for _ in ()).throw(AssertionError('unexpected start'))
result = pytest.main(['-p','pytest_django.plugin','-p','mariamem.django.pytest_plugin',
                      TEST_FILE,'--collect-only','-q'])
assert result == 0
assert config.source is None and config.manager is None
'''.replace('TEST_FILE', repr(str(test_file))))


def test_database_enabled_simple_case_is_rejected_at_collection(tmp_path):
    test_file = tmp_path / 'test_simple_database.py'
    test_file.write_text("from django.test import SimpleTestCase\n"
                         "class TestDatabase(SimpleTestCase):\n"
                         "    databases = {'default'}\n"
                         "    def test_never(self): pass\n")
    probe('''
import mariamem, os, pytest
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
mariamem.start = lambda **kw: (_ for _ in ()).throw(AssertionError('unexpected start'))
result = pytest.main(['-p','pytest_django.plugin','-p','mariamem.django.pytest_plugin',
                      TEST_FILE,'--collect-only','-q'])
assert result == pytest.ExitCode.USAGE_ERROR
assert config.source is None and config.manager is None
'''.replace('TEST_FILE', repr(str(test_file))))
