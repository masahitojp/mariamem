"""Outside-checkout owned-entry consumers; no publication or remote tags."""
import argparse
import ast
import hashlib
import json
import os
import platform
from pathlib import Path
import shutil
import signal
import zipfile
import subprocess
import sys
import tempfile

from consumer_module import MODULE, prepare_proxy, source_identity
from consumer_acceptance import verify_module_files
from git_identity import require_commit, verify_go_binary

ROOT = Path(__file__).resolve().parents[1]


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def stage_python(source):
    replacements = {
        'ROOT = Path(__file__).resolve().parents[4]': 'ROOT = Path(__file__).resolve().parent',
        'options={"host_binary": os.environ["MARIAMEM_TEST_HOST"]}': 'options={}',
    }
    for before, after in replacements.items():
        need(source.count(before) == 1, 'Python example anchor changed')
        source = source.replace(before, after)
    return source


def stage_go(source):
    before = '"../../../../tests/e2e_native_control/goapp/schema.sql"'
    need(source.count(before) == 1, 'Go example schema anchor changed')
    return source.replace(before, '"schema.sql"')


def go_cases(text):
    rows = [json.loads(line) for line in text.splitlines() if line.startswith('{')]
    need(not any(r.get('Action') in ('fail', 'skip') for r in rows), 'external Go failure/skip')
    passed = {r['Test'] for r in rows if r.get('Action') == 'pass' and r.get('Test')}
    need(passed == {'TestOwnedOrders', 'TestOwnedOrders/first', 'TestOwnedOrders/second'},
         'external Go case census differs')
    return sorted(passed)


def clean_env():
    return {k: v for k, v in os.environ.items() if k not in ('GH_TOKEN', 'GITHUB_TOKEN')
            and not k.startswith(('MARIAMEM_', 'MYSQLMEM_', 'PYTHON', 'PYTEST_'))}


def command(argv, cwd, env, log):
    with Path(log).open('w') as stream:
        proc = subprocess.Popen(list(map(str, argv)), cwd=cwd, env=env, stdout=stream,
                                stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = proc.wait(timeout=600)
        except BaseException:
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try: os.killpg(proc.pid, sig)
                except ProcessLookupError: pass
                try: proc.wait(timeout=10)
                except subprocess.TimeoutExpired: continue
            raise
    need(code == 0, 'consumer command failed: ' + Path(log).name)


def wheel_source(wheel, expected):
    record = json.loads((ROOT / 'tests/evidence/alpha-wheel.json').read_text())
    need(record.get('source_commit') == expected and record.get('sha256') == hashlib.sha256(wheel.read_bytes()).hexdigest(),
         'wheel source receipt mismatch')
    with zipfile.ZipFile(wheel) as archive:
        modules = {}
        for member in archive.namelist():
            parts = Path(member).parts
            if 'mariamem' in parts and member.endswith('.py'):
                index = max(i for i, part in enumerate(parts) if part == 'mariamem')
                relative = Path(*parts[index + 1:]).as_posix()
                need(relative not in modules and '..' not in Path(relative).parts, 'duplicate/unsafe wheel module')
                modules[relative] = archive.read(member)
        expected = {p.relative_to(ROOT / 'python/mariamem').as_posix(): p.read_bytes()
                    for p in (ROOT / 'python/mariamem').rglob('*.py') if '__pycache__' not in p.parts}
        need(modules == expected, 'wheel SDK bytes differ from candidate')


def python_consumer(work, output, wheel, expected):
    project = work / 'python'; project.mkdir()
    venv = work / 'venv'
    # The parent CI installs fixed application/browser dependencies. The SDK
    # itself must resolve from this venv's wheel, verified before resource creation.
    subprocess.run([sys.executable, '-m', 'venv', '--system-site-packages', str(venv)], check=True)
    python = venv / 'bin/python'
    env = clean_env(); env.update(E2E_OWNED_RUNTIME='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    command([python, '-m', 'pip', 'install', '--no-index', '--no-deps', wheel], work, env, output / 'wheel-install.txt')
    for directory in ('tests/e2e_native_control/pythonapp', 'tests/live_acceptance/diagnostics'):
        shutil.copytree(ROOT / directory, project / directory,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    text = stage_python((ROOT / 'docs/examples/e2e_owned/python/test_orders.py').read_text())
    (project / 'test_orders.py').write_text(text)
    # Reuse the canonical byte/inventory verifier without adding repo scripts to
    # consumer sys.path or allowing their imports to supply an SDK fallback.
    tree = ast.parse((ROOT / 'scripts/consumer_acceptance.py').read_text())
    verifier = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'verify_installed_files')
    bootstrap = '''import hashlib,json,os,sys,sysconfig,subprocess
from pathlib import Path
import mariamem
from mariamem.e2e import BrowserEntry

def require(ok, reason):
    if not ok: raise RuntimeError(reason)
'''
    bootstrap += ast.unparse(verifier) + '\n'
    bootstrap += '''package=Path(mariamem.__file__).resolve().parent
site=Path(sysconfig.get_paths("purelib")).resolve()
require(package.is_relative_to(site),"SDK imported outside installed venv")
files=verify_installed_files(Path(sys.argv[1]),package)
require("e2e.py" in files,"installed wheel lacks owned entry")
host=package/"_native/mariamem-host"
info=subprocess.check_output([sys.argv[3],"version","-m",host],text=True)
require("vcs.revision="+sys.argv[2] in info and "vcs.modified=false" in info,"bundled host source mismatch")
import pytest
code=pytest.main(["test_orders.py","--confcutdir=.","--junitxml=result.xml","-q","-s"])
require(code==0,"installed browser cases failed")
import xml.etree.ElementTree as ET
suites=list(ET.parse("result.xml").getroot().iter("testsuite"))
require(sum(int(s.get("tests",0)) for s in suites)==2,"wrong installed Python case count")
require(all(int(s.get(k,0))==0 for s in suites for k in ("failures","errors","skipped")),"hidden installed errors/skips")
Path("receipt.json").write_text(json.dumps(dict(result="PASS_INSTALLED_OWNED_PYTHON",module=str(package),files=files,host_sha256=hashlib.sha256(host.read_bytes()).hexdigest(),cases=2,python=sys.version),indent=2)+"\\n")
'''
    (project / 'bootstrap.py').write_text(bootstrap)
    go = shutil.which('go'); need(go is not None, 'Go binary required for bundled-host identity')
    command([python, '-I', project / 'bootstrap.py', wheel, expected, go], project, env, output / 'python-runtime.txt')
    shutil.copyfile(project / 'result.xml', output / 'python-junit.xml')
    return json.loads((project / 'receipt.json').read_text())


def go_consumer(work, output, app):
    # Reuse G1's identical content-addressed module fixture/cache, not a release.
    tag = 'v0.0.0-g1.' + source_identity(ROOT)[:16]
    proxy = prepare_proxy(ROOT, work, tag)
    project = work / 'go'; project.mkdir()
    (project / 'entry_test.go').write_text(stage_go((ROOT / 'docs/examples/e2e_owned/go/entry_test.go').read_text()))
    shutil.copyfile(ROOT / 'tests/e2e_native_control/goapp/schema.sql', project / 'schema.sql')
    (project / 'go.mod').write_text('module example.com/owned-consumer\n\ngo 1.26.0\n\nrequire ' + MODULE + ' ' + tag + '\n')
    shutil.copyfile(ROOT / 'go.sum', project / 'go.sum')
    compiler = Path(subprocess.check_output(['go', 'env', 'GOROOT'], text=True).strip()) / 'bin/go'
    env = {k: v for k, v in clean_env().items() if not k.startswith('GO')}
    env.update(GOWORK='off', GOENV='off', GOTOOLCHAIN='local', GOFLAGS='-p=1 -trimpath',
               CGO_ENABLED='0', GOPROXY=proxy.as_uri() + ',https://proxy.golang.org',
               GONOSUMDB=MODULE, GOSUMDB='sum.golang.org', E2E_OWNED_RUNTIME='1', E2E_GO_APP=str(app))
    need(subprocess.check_output([compiler, 'version'], env=env, text=True).split()[2] == 'go1.26.10', 'wrong consumer compiler')
    command([compiler, 'mod', 'download', MODULE + '@' + tag], project,
            dict(env, GOPROXY=proxy.as_uri()), output / 'go-download.txt')
    command([compiler, 'mod', 'tidy'], project, env, output / 'go-tidy.txt')
    resolved = json.loads(subprocess.check_output([compiler, 'list', '-m', '-json', MODULE], cwd=project, env=env, text=True))
    need(resolved.get('Path') == MODULE and resolved.get('Version') == tag and 'Replace' not in resolved,
         'consumer module replaced or wrong version')
    need(not Path(resolved['Dir']).resolve().is_relative_to(ROOT), 'consumer used source checkout')
    need(str(resolved.get('Sum', '')).startswith('h1:'), 'module checksum missing')
    inventory = verify_module_files(resolved, ROOT)
    need(subprocess.check_output([compiler, 'env', 'GOMOD'], cwd=project, env=env, text=True).strip() == str(project / 'go.mod'), 'wrong consumer workspace')
    command([compiler, 'test', '-json', '-count=1', '.'], project, env, output / 'go-runtime.jsonl.txt')
    return dict(result='PASS_EXTERNAL_OWNED_GO', private_version=tag, replace=False,
                module_files=inventory, module_sum=resolved.get('Sum'),
                cases=go_cases((output / 'go-runtime.jsonl.txt').read_text()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-source-commit', required=True)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--go-app', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require_commit(ROOT, args.expected_source_commit)
    need(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == args.expected_source_commit
         and not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT), 'exact clean source required')
    wheel, app, output = args.wheel.resolve(), args.go_app.resolve(), args.output.resolve()
    verify_go_binary(ROOT, app, args.expected_source_commit)
    wheel_source(wheel, args.expected_source_commit)
    output.mkdir(parents=True, exist_ok=False)
    data = dict(source_commit=args.expected_source_commit, result='RUNNING',
                host=dict(system=platform.system(), architecture=platform.machine(), platform=platform.platform()),
                python_minor=f'{sys.version_info.major}.{sys.version_info.minor}',
                wheel_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest())
    try:
        with tempfile.TemporaryDirectory(prefix='mariamem-owned-consumer-') as temporary:
            work = Path(temporary).resolve()
            need(not work.is_relative_to(ROOT), 'consumer must be outside checkout')
            data['python'] = python_consumer(work, output, wheel, args.expected_source_commit)
            data['go'] = go_consumer(work, output, app)
        data.update(result='PASS_INSTALLED_OWNED', temporary_cleanup='complete')
    except BaseException as error:
        data.update(result='FAIL', error=str(error), runtime_cleanup='unconfirmed')
        raise
    finally:
        (output / 'result.json').write_text(json.dumps(data, indent=2) + '\n')
        (output / 'SHA256SUMS.json').write_text(json.dumps({p.name: hashlib.sha256(p.read_bytes()).hexdigest()
             for p in output.iterdir() if p.is_file() and p.name != 'SHA256SUMS.json'}, indent=2) + '\n')


if __name__ == '__main__':
    main()
