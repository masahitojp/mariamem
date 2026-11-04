"""Execute public Python lifecycle snippets with an explicit development host.

Installation commands and pytest fixture definitions have different owners.
The only substitution selects the locally built host; product calls stay intact.
"""
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def python_lifecycle_blocks(text):
    """Extract manual snippets, regardless of the pytest section's position."""
    sections = re.split(r'(?m)(^## .*\n)', text)
    included = [sections[0]]
    for index in range(1, len(sections), 2):
        heading, body = sections[index:index + 2]
        if heading.strip() not in ('## pytest fixtures', '## Installation'):
            included.append(body)
    return re.findall(r'```python\n(.*?)```', '\n'.join(included), re.S)


@pytest.mark.parametrize('fixture_first', [False, True])
def test_manual_extraction_survives_fixture_section_reordering(fixture_first):
    fixture = '## pytest fixtures\n```python\n@pytest.fixture\ndef baseline(): pass\n```\n'
    manual = '## Share preparation, isolate mutations\n```python\nwith source.snapshot() as saved: pass\n```\n'
    installation = '## Installation\n```python\ninstall_only()\n```\n'
    text = installation + (fixture + manual if fixture_first else manual + fixture)
    assert python_lifecycle_blocks(text) == ['with source.snapshot() as saved: pass\n']


@pytest.mark.parametrize('document', ['README.md', 'docs/python.md'])
def test_python_lifecycle_examples(document, tmp_path):
    host = os.environ.get('MARIAMEM_TEST_HOST')
    if not host:
        pytest.skip('requires real host')
    blocks = python_lifecycle_blocks((ROOT / document).read_text())
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


EXAMPLES = ROOT / 'docs/examples/live'
spec = importlib.util.spec_from_file_location('live_example_verify', EXAMPLES / 'verify.py')
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)


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


@pytest.mark.parametrize('skip_go,fail_go', [(False,False),(True,False),(False,True)])
def test_examples_cli_preserves_language_census_and_failures(tmp_path, monkeypatch, skip_go, fail_go):
    from types import SimpleNamespace
    calls=[]
    monkeypatch.setattr(owner,'require_commit',lambda *args:SimpleNamespace(source_commit='a'*40))
    monkeypatch.setattr(owner,'inspect_ref',lambda *args:SimpleNamespace(source_commit='a'*40))
    monkeypatch.setattr(owner,'verify_go_binary',lambda *args:{'source_commit':'a'*40})
    output=tmp_path/'examples'
    def run(command, **kwargs):
        kind='go' if command[0]=='go' else 'python';calls.append(kind)
        if kind=='go':
            kwargs['stdout'].write('\n'.join(json.dumps(dict(Action='pass',Test=n)) for n in
                ('TestOrders','TestOrders/first','TestOrders/second')))
        else:
            (output/'pytest.xml').write_text('<testsuites><testsuite tests="2" skipped="0" failures="0" errors="0"/></testsuites>')
        return SimpleNamespace(returncode=int(kind=='go' and fail_go))
    monkeypatch.setattr(owner.subprocess,'run',run)
    monkeypatch.setattr(sys,'argv',['verify.py','--host',str(tmp_path/'host'),'--go-app',str(tmp_path/'app'),
        '--expected-source-commit','a'*40,'--output',str(output)]+(['--skip-go'] if skip_go else []))
    assert owner.main()==int(fail_go)
    receipt=json.loads((output/'result.json').read_text())
    assert calls==(['python'] if skip_go else ['go','python'])
    assert receipt['selected_languages']==calls
    assert (receipt['result']=='FAIL')==fail_go
