"""Pure owner/error and source-binding checks; no Django, DB or Go execution."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'tests/django_lifecycle'


def load(name, path, monkeypatch):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def recipe(monkeypatch):
    events = []
    class Owner:
        def __enter__(self):
            events.append('start')
            return self
        def connection_info(self):
            return dict(host='127.0.0.1', port=12345, database='mariamem')
        def __exit__(self, *error):
            events.append(('closed', error[0]))
    monkeypatch.setitem(sys.modules, 'mariamem', SimpleNamespace(start=lambda **kwargs: Owner()))
    return load('django_recipe', ROOT / 'docs/examples/django/run_tests.py', monkeypatch), events


@pytest.mark.parametrize('runner', ['manage', 'pytest'])
@pytest.mark.parametrize('code', [0, 1, 5])
def test_original_exit_after_owner_cleanup(recipe, monkeypatch, tmp_path, runner, code):
    module, events = recipe
    observed = {}
    def run(command, **kwargs):
        observed.update(command=command, **kwargs)
        events.append('test-process')
        return SimpleNamespace(returncode=code)
    monkeypatch.setattr(module.subprocess, 'run', run)
    assert module.main(['--host', str(tmp_path / 'host'), '--project', str(tmp_path),
                        '--settings', 'myproject.test_settings', '--runner', runner, '--', 'selected']) == code
    assert events == ['start', 'test-process', ('closed', None)]
    command = observed['command']
    assert command[0] == sys.executable and command[-1] == 'selected'
    assert command[1:-1] == ([str(tmp_path / 'manage.py'), 'test', '--noinput']
                              if runner == 'manage' else ['-m', 'pytest'])
    assert observed['env']['E2E_DB_PORT'] == '12345'
    assert observed['env']['DJANGO_SETTINGS_MODULE'] == 'myproject.test_settings'
    assert observed['cwd'] == tmp_path and observed['timeout'] == 120
    # Child stdout/stderr and original migration tracebacks remain inherited.
    assert not {'stdout', 'stderr', 'capture_output'} & observed.keys()


@pytest.mark.parametrize('error', [subprocess.TimeoutExpired(['test'], 1), OSError('spawn failed'), KeyboardInterrupt()])
def test_exception_still_discards_owner(recipe, monkeypatch, tmp_path, error):
    module, events = recipe
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(module.subprocess, 'run', fail)
    with pytest.raises(type(error)) as raised:
        module.main(['--host', str(tmp_path / 'host'), '--project', str(tmp_path), '--settings', 'settings'])
    assert raised.value is error
    assert events == ['start', ('closed', type(error))]


@pytest.fixture
def ci(monkeypatch):
    monkeypatch.syspath_prepend(str(HERE))
    load('run', HERE / 'run.py', monkeypatch)
    load('run_mixed', HERE / 'run_mixed.py', monkeypatch)
    return load('django_recipe_ci', HERE / 'ci.py', monkeypatch)


@pytest.fixture
def reference(ci):
    sha = 'a' * 40
    pin = json.loads(ci.PIN.read_text())
    acquisition = {key: pin[key] for key in ['host', 'image_ref', 'image', 'programs', 'startup_query']}
    acquisition.update(source=dict(object_type='commit', object_sha=sha, source_commit=sha), container_image=pin['image']['id'])
    return dict(result='PASS', source_commit=sha, inputs={'sha256': {}}, python_minor='3.14',
                host=dict(system='Linux', machine='x86_64'), acquisition=acquisition,
                suites={name: dict(result='PASS') for name in ci.suite_names()},
                failures={name: dict(result='PASS_FAILURE_DETECTED_BEFORE_TEST_BODY') for name in ['manage', 'pytest']},
                native_schemas_removed=True)


def test_complete_reference(ci, reference):
    ci.check_reference(reference, 'a' * 40, {'sha256': {}}, '3.14')


@pytest.mark.parametrize('mutation', ['source', 'inputs', 'minor', 'host', 'image', 'program', 'missing_suite',
                                     'failed_suite', 'missing_failure', 'failed_failure', 'cleanup', 'result'])
def test_reference_rejects_stale_partial_or_wrong_native(ci, reference, mutation):
    value = copy.deepcopy(reference)
    if mutation == 'source': value['source_commit'] = 'b' * 40
    elif mutation == 'inputs': value['inputs']['sha256']['changed'] = 'x'
    elif mutation == 'minor': value['python_minor'] = '3.11'
    elif mutation == 'host': value['host']['machine'] = 'arm64'
    elif mutation == 'image': value['acquisition']['container_image'] = 'wrong'
    elif mutation == 'program': value['acquisition']['programs']['mariadbd']['sha256'] = 'wrong'
    elif mutation == 'missing_suite': value['suites'].pop(next(iter(value['suites'])))
    elif mutation == 'failed_suite': value['suites'][next(iter(value['suites']))]['result'] = 'FAIL'
    elif mutation == 'missing_failure': value['failures'].pop('manage')
    elif mutation == 'failed_failure': value['failures']['manage']['result'] = 'SKIP'
    elif mutation == 'cleanup': value['native_schemas_removed'] = False
    elif mutation == 'result': value['result'] = 'FAIL'
    with pytest.raises(ValueError):
        ci.check_reference(value, 'a' * 40, {'sha256': {}}, '3.14')


def test_authored_inputs_and_pins_preserved():
    manifest = json.loads((HERE / 'input-manifest.json').read_text())
    assert len(manifest['application_sha256']) == 13
    for name, expected in manifest['application_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    assert manifest['versions'] == {'Django': '5.2.8', 'mysqlclient': '2.2.7', 'pytest': '9.0.2', 'pytest-django': '4.12.0'}


def test_comparison_keeps_error_semantics_but_excludes_unique_paths(ci):
    first = dict(summary=dict(failures=[dict(name='expected-test', message='/one/path: original failure')]),
                 setup_failures=[dict(errors=[dict(type='MySQLdb.ProgrammingError', args=[1146, 'one.table'], message='one.table')])])
    second = copy.deepcopy(first)
    second['summary']['failures'][0]['message'] = '/another/path: original failure'
    second['setup_failures'][0]['errors'][0].update(args=[1146, 'two.table'], message='two.table')
    assert ci.comparable(first) == ci.comparable(second)
    second['setup_failures'][0]['errors'][0]['args'][0] = 1064
    assert ci.comparable(first) != ci.comparable(second)
