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
    source = source.replace('mariamem.load_snapshot("./prepared")', f'mariamem.load_snapshot("./prepared", host_binary={host!r})')
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
