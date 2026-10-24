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
        def mariamem_route_engines():
            return (create_engine('mysql+pymysql://u@127.0.0.1:3307/app'),)
    '''))
    (tmp_path / "test_app.py").write_text(textwrap.dedent('''
        import pytest
        pytestmark=pytest.mark.usefixtures('mariamem_routed')
        def test_first(mariamem_routes):
            assert mariamem_routes._target().child_id=='test_first'
        def test_second(mariamem_routes):
            assert mariamem_routes._target().child_id=='test_second'
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
            r=pytestconfig._mariamem_routes
            class Child:
                closed=False
                id=os.environ['PYTEST_XDIST_WORKER']
            with r.bind('app',Child()):
                assert r._target().child_id==os.environ['PYTEST_XDIST_WORKER']
    '''))
    result = run(tmp_path, "-p", "xdist.plugin", "-n", "2")
    assert result.returncode == 0, result.stdout + result.stderr
