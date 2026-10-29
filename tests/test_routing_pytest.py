"""Early-plugin/lifecycle tests in fresh interpreters, without a guest build."""
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

PYTHON = Path(__file__).resolve().parents[1] / "python"
CONFIG = "[pytest]\nmariamem_route_profiles = app = 127.0.0.1:3307/app\n"


def run(directory, *arguments, script=None):
    env = dict(os.environ, PYTHONPATH=str(PYTHON), PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    env.pop("PYTEST_ADDOPTS", None)
    args = [sys.executable, "-c", script] if script else [sys.executable, "-m", "pytest", "-p", "mariamem.pytest_plugin", "-q", *arguments]
    return subprocess.run(args, cwd=directory, env=env, capture_output=True, text=True, timeout=30)


@pytest.mark.parametrize("location", ["conftest", "module"])
@pytest.mark.parametrize("configuration", ["ini", "cli"])
def test_guard_is_active_before_application_imports(tmp_path, location, configuration):
    if configuration == "ini":
        (tmp_path / "pytest.ini").write_text(CONFIG)
    probe = '''
import pymysql
from mariamem.routing import RoutingError
try:
    pymysql.connect(host='127.0.0.1',port=3307,database='app',user='u',password='do-not-print')
except RoutingError as error:
    assert error.code == 'missing_target'
else:
    raise AssertionError('original endpoint attempted')
'''
    (tmp_path / "conftest.py").write_text(probe if location == "conftest" else "")
    (tmp_path / "test_app.py").write_text((probe if location == "module" else "") + "\ndef test_application(): pass\n")
    args = ("--mariamem-route", "app=127.0.0.1:3307/app") if configuration == "cli" else ()
    result = run(tmp_path, *args)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "do-not-print" not in result.stderr


def test_no_config_does_not_import_or_patch_driver(tmp_path):
    (tmp_path / "test_empty.py").write_text("def test_empty():\n import sys\n assert 'pymysql' not in sys.modules\n assert 'sqlalchemy' not in sys.modules\n")
    result = run(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_collection_failure_restores_hooks(tmp_path):
    (tmp_path / "pytest.ini").write_text(CONFIG)
    (tmp_path / "test_bad.py").write_text("raise ValueError('collection failure')\n")
    script = '''
import pytest,pymysql
before=pymysql.connections.Connection.connect
code=pytest.main(['-p','mariamem.pytest_plugin','-q'])
assert code != 0
assert pymysql.connections.Connection.connect is before
from mariamem import routing
assert routing._active is None
'''
    result = run(tmp_path, script=script)
    assert result.returncode == 0, result.stdout + result.stderr


def test_malformed_configuration_does_not_echo_credentials(tmp_path):
    (tmp_path / "pytest.ini").write_text("[pytest]\nmariamem_route_profiles = app=127.0.0.1:private-port-value/app\n")
    result = run(tmp_path)
    assert result.returncode != 0
    assert "private-port-value" not in result.stdout + result.stderr


def test_routed_fixture_owns_only_binding_and_separate_children(tmp_path):
    (tmp_path / "pytest.ini").write_text(CONFIG)
    (tmp_path / "conftest.py").write_text(textwrap.dedent('''
        import pytest
        from sqlalchemy import create_engine
        class Child:
            closed=False
            def __init__(self,id): self.id=id
            def wait_disconnected(self): pass
        @pytest.fixture
        def mariamem_fork(request):
            child=Child(request.node.name)
            yield child
            child.closed=True
        @pytest.fixture(scope='session')
        def mariamem_sqlalchemy_engines():
            return (create_engine('mysql+pymysql://u@127.0.0.1:3307/app'),)
    '''))
    (tmp_path / "test_app.py").write_text(textwrap.dedent('''
        import pytest
        pytestmark=pytest.mark.usefixtures('mariamem_app_db')
        def test_first(mariamem_router):
            assert mariamem_router._target().child_id=='test_first'
        def test_second(mariamem_router):
            assert mariamem_router._target().child_id=='test_second'
    '''))
    result = run(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_worker_local_registry(tmp_path):
    (tmp_path / "pytest.ini").write_text(CONFIG)
    (tmp_path / "test_worker.py").write_text(textwrap.dedent('''
        import os,pytest
        from mariamem import routing
        @pytest.mark.parametrize('n',range(4))
        def test_worker(n,pytestconfig):
            r=pytestconfig._mariamem_router
            class Child:
                closed=False
                id=os.environ['PYTEST_XDIST_WORKER']
            with r.bind('app',Child()):
                assert r._target().child_id==os.environ['PYTEST_XDIST_WORKER']
    '''))
    result = run(tmp_path, "-p", "xdist.plugin", "-n", "2")
    assert result.returncode == 0, result.stdout + result.stderr


FAKE_RUNTIME = '''
import json, os
from pathlib import Path
from contextlib import contextmanager
import pytest
import mariamem.pytest_plugin as plugin

def record(name):
    with Path('events-' + os.environ.get('PYTEST_XDIST_WORKER', 'main') + '.jsonl').open('a') as out:
        out.write(json.dumps(name) + '\\n')

class DB:
    closed = False
    def __init__(self, name, data=None):
        self.id = name
        self.data = dict(data or {})
    def wait_disconnected(self):
        record('wait:' + self.id)
        if self.data.get('fail_wait'):
            raise RuntimeError('preparation still connected')
    @contextmanager
    def snapshot(self):
        record('snapshot')
        self.closed = True
        try:
            yield Baseline(self.data)
        finally:
            record('baseline.close')

class Baseline:
    def __init__(self, data): self.data = dict(data)
    @contextmanager
    def fork(self):
        record('fork')
        child = DB('child', self.data)
        try: yield child
        finally:
            child.closed = True
            record('child.close')

@contextmanager
def start(**options):
    record('start')
    source = DB('source')
    try: yield source
    finally:
        source.closed = True
        record('source.close')

plugin.start = start
'''


def fake_suite(directory, conftest='', tests='', configured=True, *arguments):
    if configured:
        (directory / 'pytest.ini').write_text(CONFIG)
    (directory / 'conftest.py').write_text(FAKE_RUNTIME + textwrap.dedent(conftest))
    (directory / 'test_app.py').write_text(textwrap.dedent(tests))
    result = run(directory, *arguments)
    events = []
    for path in directory.glob('events-*.jsonl'):
        import json
        events.extend(json.loads(line) for line in path.read_text().splitlines())
    return result, events


@pytest.mark.parametrize('scope', ['function', 'class', 'module', 'fixture_only'])
def test_marker_and_fixture_share_child_binding_and_order(tmp_path, scope):
    body = '''
        import pytest
        @pytest.fixture
        def application(mariamem_router):
            target = mariamem_router._target()
            assert target.database.data == {'seed': 1}
            yield target
            assert target.live
        def test_first(application, mariamem_app_db, mariamem_fork, mariamem_router):
            assert mariamem_app_db is mariamem_fork
            assert application is mariamem_router._target()
            assert application.database is mariamem_app_db
            mariamem_app_db.data['change'] = 2
        def test_second(mariamem_app_db):
            assert mariamem_app_db.data == {'seed': 1}
    '''
    body = textwrap.dedent(body)
    if scope == 'function':
        body = body.replace('def test_', '@pytest.mark.shadow_maria\ndef test_')
    elif scope == 'module':
        body = 'import pytest\npytestmark = pytest.mark.shadow_maria\n' + body
    elif scope == 'class':
        body = 'import pytest\n@pytest.mark.shadow_maria\nclass TestApplication:\n' + textwrap.indent(body.replace('def test_first(', 'def test_first(self, ').replace('def test_second(', 'def test_second(self, ').replace('def application(', 'def application(self, '), '    ')
    else:
        body = body.replace('def application(mariamem_router)', 'def application(mariamem_app_db, mariamem_router)')
    result, events = fake_suite(tmp_path, '''
        @pytest.fixture(scope='session')
        def mariamem_prepare():
            def prepare(db):
                record('prepare')
                db.data['seed'] = 1
            return prepare
    ''', body)
    assert result.returncode == 0, result.stdout + result.stderr
    assert events.count('prepare') == events.count('snapshot') == 1
    assert events.count('fork') == events.count('child.close') == 2
    assert events[:4] == ['start', 'prepare', 'wait:source', 'snapshot']
    assert events[-2:] == ['baseline.close', 'source.close']


@pytest.mark.parametrize('argument', ['True', 'fork=True', 'fork=False', 'live=True', 'prepare=True', "profile='app'"])
def test_marker_arguments_rejected_before_start(tmp_path, argument):
    result, events = fake_suite(tmp_path, tests=f'''
        import pytest
        @pytest.mark.shadow_maria({argument})
        def test_app(): pass
    ''')
    assert result.returncode == 4, result.stdout + result.stderr
    assert 'shadow_maria accepts no arguments' in result.stderr
    assert events == []


@pytest.mark.parametrize('configured', [False, True])
def test_unmarked_tests_do_not_start_database(tmp_path, configured):
    result, events = fake_suite(tmp_path, tests='def test_app(): pass', configured=configured)
    assert result.returncode == 0, result.stdout + result.stderr
    assert events == []


@pytest.mark.parametrize('prepare', ['default', 'side_effect', 'callback'])
def test_prepare_none_or_callable_runs_once(tmp_path, prepare):
    override = ''
    if prepare == 'side_effect':
        override = '''
        @pytest.fixture(scope='session')
        def mariamem_prepare(mariamem_server):
            record('prepare')
            mariamem_server.data['seed'] = 1
        '''
    elif prepare == 'callback':
        override = '''
        @pytest.fixture(scope='session')
        def mariamem_prepare():
            def prepare(db):
                record('prepare')
                db.data['seed'] = 1
                return 'unused callback result'
            return prepare
        '''
    result, events = fake_suite(tmp_path, override, '''
        def test_first(mariamem_fork): pass
        def test_second(mariamem_fork): pass
    ''', configured=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert events.count('prepare') == (0 if prepare == 'default' else 1)
    assert events.count('snapshot') == 1 and events.count('fork') == 2


@pytest.mark.parametrize('failure', ['invalid', 'callback', 'setup', 'wait'])
def test_preparation_failure_prevents_snapshot_and_closes_source(tmp_path, failure):
    override = {
        'invalid': "return 42",
        'callback': "def prepare(db):\n    raise ValueError('original preparation failure')\nreturn prepare",
        'setup': "raise LookupError('original fixture failure')",
        'wait': "return lambda db: db.data.update(fail_wait=True)",
    }[failure]
    conf = "\n@pytest.fixture(scope='session')\ndef mariamem_prepare():\n" + textwrap.indent(override, '    ') + '\n'
    result, events = fake_suite(tmp_path, conf, 'def test_app(mariamem_app_db): pass')
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'snapshot' not in events and 'fork' not in events
    assert events[-1] == 'source.close'
    expected = {'invalid':'must return None, a callable', 'callback':'ValueError: original preparation failure', 'setup':'LookupError: original fixture failure', 'wait':'preparation still connected'}[failure]
    assert expected in result.stdout + result.stderr


@pytest.mark.parametrize('boundary', ['server', 'snapshot', 'fork'])
def test_existing_fixture_overrides_own_their_boundary(tmp_path, boundary):
    conf = '''
@pytest.fixture(scope='session')
def mariamem_prepare():
    def prepare(db):
        record('prepare:' + db.id)
    return prepare
'''
    if boundary == 'server':
        conf += '''
@pytest.fixture(scope='session')
def mariamem_server():
    yield DB('custom-source')
'''
    elif boundary == 'snapshot':
        conf += '''
@pytest.fixture(scope='session')
def mariamem_snapshot():
    yield Baseline({})
'''
    else:
        conf += '''
@pytest.fixture
def mariamem_fork():
    yield DB('custom-child')
'''
    result, events = fake_suite(tmp_path, conf, 'def test_app(mariamem_app_db): pass')
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'start' not in events
    assert ('prepare:custom-source' in events) == (boundary == 'server')
    assert ('snapshot' in events) == (boundary == 'server')
    assert events.count('fork') == (0 if boundary == 'fork' else 1)


def test_prepare_does_not_redirect_original_application_connections(tmp_path):
    result, events = fake_suite(tmp_path, '''
        @pytest.fixture(scope='session')
        def mariamem_prepare():
            def prepare(db):
                import pymysql
                from mariamem.routing import RoutingError
                with pytest.raises(RoutingError, match='missing_target'):
                    pymysql.connect(host='127.0.0.1', port=3307, database='app')
            return prepare
    ''', 'def test_app(mariamem_app_db): pass')
    assert result.returncode == 0, result.stdout + result.stderr
    assert events.count('snapshot') == 1


def test_marker_alone_activates_binding_for_application_fixture(tmp_path):
    result, events = fake_suite(tmp_path, tests='''
        import pytest
        @pytest.fixture
        def application(mariamem_router):
            assert mariamem_router._target().database.id == 'child'
            yield
            assert mariamem_router._target().live
        @pytest.mark.shadow_maria
        def test_app(application): pass
    ''')
    assert result.returncode == 0, result.stdout + result.stderr
    assert events.count('fork') == 1


def test_prepare_runs_once_per_worker(tmp_path):
    result, events = fake_suite(tmp_path, '''
        @pytest.fixture(scope='session')
        def mariamem_prepare():
            def prepare(db):
                record('prepare')
                db.data['seed'] = 1
            return prepare
    ''', '''
        import pytest
        pytestmark = pytest.mark.shadow_maria
        @pytest.mark.parametrize('number', range(4))
        def test_app(number, mariamem_app_db):
            assert mariamem_app_db.data == {'seed': 1}
            mariamem_app_db.data['changed'] = True
    ''', True, '-p', 'xdist.plugin', '-n', '2')
    assert result.returncode == 0, result.stdout + result.stderr
    assert events.count('prepare') == events.count('snapshot') == 2
    assert events.count('fork') == events.count('child.close') == 4


def test_public_names_and_python_floor():
    import configparser
    from packaging.specifiers import SpecifierSet
    from mariamem import routing
    from mariamem import pytest_plugin
    assert not hasattr(routing, 'Registry')
    assert not hasattr(routing.Router, 'enroll')
    for name in ['mariamem_routed', 'mariamem_routes', 'mariamem_route_engines']:
        assert not hasattr(pytest_plugin, name)
    config = configparser.ConfigParser()
    config.read(PYTHON / 'setup.cfg')
    supported = SpecifierSet(config['options']['python_requires'])
    assert '3.11' in supported and '3.14' in supported
    assert '3.9' not in supported and '3.10' not in supported
    assert 'routing-pymysql' in config['options.extras_require']
    assert 'routing-mysql-connector' in config['options.extras_require']
    assert 'routing' not in config['options.extras_require']
    assert 'routing-connector' not in config['options.extras_require']
