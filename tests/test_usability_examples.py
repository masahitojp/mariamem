"""Execute public Python lifecycle snippets with an explicit development host.

Installation commands and pytest fixture definitions have different owners.
The only substitution selects the locally built host; product calls stay intact.
"""
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('document', ['README.md', 'docs/python.md'])
def test_python_lifecycle_examples(document, tmp_path):
    host = os.environ.get('MARIAMEM_TEST_HOST')
    if not host:
        pytest.skip('requires real host')
    text = (ROOT / document).read_text().split('## pytest fixtures')[0]
    blocks = re.findall(r'```python\n(.*?)```', text, re.S)
    assert blocks
    source = 'import mariamem\nimport pymysql\n' + '\n'.join(blocks)
    source = source.replace('mariamem.start(snapshot=baseline)', f'mariamem.start(snapshot=baseline, host_binary={host!r})')
    source = source.replace('mariamem.start()', f'mariamem.start(host_binary={host!r})')
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'python'))
    subprocess.run([sys.executable, '-c', source], cwd=tmp_path, env=env,
                   check=True, timeout=120)


def test_go_lifecycle_examples(tmp_path):
    if not os.environ.get('MARIAMEM_TEST_HOST'):
        pytest.skip('requires real host and local compiler')
    sys.path.insert(0, str(ROOT / 'scripts'))
    from consumer_module import prepare_proxy
    proxy = prepare_proxy(ROOT, tmp_path, 'v0.4.5')
    project = tmp_path / 'consumer'
    project.mkdir()
    (project / 'go.mod').write_text('module example.com/docs\n\ngo 1.26.0\n\nrequire (\n github.com/masahitojp/mariamem v0.4.5\n github.com/go-sql-driver/mysql v1.9.3\n)\n')
    for document in ('README.md', 'docs/go.md'):
        blocks = re.findall(r'```go\n(.*?)```', (ROOT / document).read_text(), re.S)
        assert blocks
        for index, block in enumerate(blocks):
            if block.startswith('package example'):
                source = block
            else:
                # Fragment context declared in the guide: a started, prepared DB.
                source = '''package example
import("context";"testing";"github.com/masahitojp/mariamem")
func TestFragment(t *testing.T) { if err:=example();err!=nil {t.Fatal(err)} }
func example() error {
ctx:=context.Background()
setupDB,err:=mariamem.Start(ctx,mariamem.Options{})
if err!=nil {return err}
defer setupDB.Close()
''' + block + '\nreturn nil\n}\n'
            path = project / 'example_test.go'
            path.write_text(source)
            env = dict(os.environ, GOTOOLCHAIN='local', GOWORK='off',
                       GOPROXY=proxy.as_uri()+',https://proxy.golang.org',
                       GONOSUMDB='github.com/masahitojp/mariamem')
            # Each fragment owns a disposable working directory/artifact.
            subprocess.run(['go', 'test', '-p', '1', '-mod=mod', '-count=1', '.'],
                           cwd=project, env=env, check=True, timeout=300)
            import shutil
            shutil.rmtree(project / 'prepared', ignore_errors=True)


"""Focused structure and result-oracle checks; no guest or browser execution."""
import ast
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / 'docs/examples/live'
spec = importlib.util.spec_from_file_location('live_example_verify', EXAMPLES / 'verify.py')
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)


def test_python_example_structure():
    path = EXAMPLES / 'python/test_orders.py'
    tree = ast.parse(path.read_text())
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    application = ast.get_source_segment(path.read_text(), funcs['application'])
    page = ast.get_source_segment(path.read_text(), funcs['page'])
    assert application.count("manage(env, 'migrate', '--noinput')") == 1
    assert application.index('source.wait_disconnected()') < application.index('source.snapshot()')
    assert application.index('prepared.live()') < application.index('subprocess.Popen(')
    assert 'app.wait(timeout=5)' in application
    assert page.index("assert state['admission_open']") < page.index('live.reset(')
    assert page.index("state['admission_open'] = False") < page.index('live.reset(')
    assert page.index('live.reset(') < page.index('browser.new_context()')
    assert "['SEED:2:ready']" in page
    assert "['SEED:2:ready', 'NEW:3:ready']" in path.read_text()
    assert '._session' not in path.read_text()


def test_go_example_and_maintained_inputs():
    source = (EXAMPLES / 'go/live_test.go').read_text()
    assert 'if !t.Run(name,' in source and 'stop admitting tests' in source
    assert source.index('pool.Close(); err') < source.index('source.Snapshot(')
    assert 'if live != nil {' in source
    assert source.index('prepared.Live(ctx)') < source.index('app.Start()')
    assert 'live.ConnectionInfo() != endpoint' in source
    assert 'SEED:2:ready' in source and 'NEW:3:ready' in source
    assert 'tests/e2e_native_control/goapp/schema.sql' in source
    assert 'db.SetMaxIdleConns(0)' in (ROOT / 'tests/live_acceptance/goapp/main.go').read_text()
    assert 'CONN_MAX_AGE' in (ROOT / 'tests/e2e_native_control/pythonapp/settings.py').read_text()


@pytest.mark.parametrize('action', ['pass', 'fail', 'skip'])
def test_go_result_requires_both_cases_without_skips(tmp_path, action):
    log = tmp_path / 'go.json'
    log.write_text('\n'.join(json.dumps(dict(Action=a, Test=n)) for n, a in [
        ('TestOrders', 'pass'), ('TestOrders/first', 'pass'), ('TestOrders/second', action)]))
    assert owner.go_passed(log) == (action == 'pass')


@pytest.mark.parametrize('tests,skips,failures,accepted', [(2, 0, 0, True), (1, 0, 0, False),
                                                        (2, 1, 0, False), (2, 0, 1, False)])
def test_python_result_requires_two_executed_cases(tmp_path, tests, skips, failures, accepted):
    result = tmp_path / 'pytest.xml'
    result.write_text(f'<testsuites><testsuite tests="{tests}" skipped="{skips}" failures="{failures}" errors="0"/></testsuites>')
    assert owner.python_passed(result) == accepted


def test_workflow_executes_exact_examples_and_keeps_existing_owners():
    workflow = (ROOT / '.github/workflows/live-host.yml').read_text()
    assert 'docs/examples/live/verify.py --host build/mariamem-host --go-app build/go-live-orders' in workflow
    for existing in ['tests/live_acceptance/native.py', 'tests/live_acceptance/run.py',
                     'tests/live_acceptance/installed.py', 'positive skip-reset restart-app']:
        assert existing in workflow
