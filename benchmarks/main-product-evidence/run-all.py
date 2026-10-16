"""Run the finite identity-bound campaign serially under experiment_workspace."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--go-root', type=Path, required=True)
a = p.parse_args()
w = a.workspace.resolve()
root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'scripts'))
from git_identity import read_release_pin, require_commit, verify_go_binary, verify_release_pin
sources = {'baseline': '44100ec676c8c9064f32f3a01bd9a990d487bb61', 'candidate': 'c97e55fc065f6ee7b560325077726da53e5d95d7'}
verify_release_pin(root, read_release_pin(root / 'release/baselines/v0.5.0.json'))
for label, source in sources.items():
    checkout = w / 'temp' / label
    require_commit(checkout, source)
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=checkout, text=True).strip() == source
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=checkout)
env = {k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_', 'MYSQLMEM_'))}
env['PATH'] = str(a.go_root / 'bin') + os.pathsep + env['PATH']
env['GOTOOLCHAIN'] = 'local'
env.pop('GOMAXPROCS', None)
env.pop('GOMEMLIMIT', None)
env.pop('GOGC', None)
# Every dependency/cache/build output belongs to this disposable task.
for key, name in [('GOPATH','go-path'),('GOMODCACHE','go-mod'),('GOCACHE','go-cache'),('GOTMPDIR','go-tmp')]:
    env[key] = str(w / 'temp' / name)
subprocess.run([sys.executable, str(Path(__file__).with_name('build-pair.py')), '--workspace', str(w), '--go-root', str(a.go_root)], env=env, check=True)
for label, source in sources.items():
    for binary in ['mariamem-host', 'ownedprepared']:
        verify_go_binary(w / 'temp' / label, w / 'temp/binaries' / label / binary, source, go=a.go_root / 'bin/go')
(w / 'evidence/python-dependencies.txt').write_text(subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True))
subprocess.run([sys.executable, str(Path(__file__).with_name('run-product.py')), '--workspace', str(w), '--output', str(w / 'evidence/matrix')], env=env, check=True)
shared = [sys.executable, str(root / 'benchmarks/sharedhost/campaign.py')]
for label, source in sources.items():
    shared += ['--'+label, str(w / 'temp' / label), '--'+label+'-commit', source, '--'+label+'-host', str(w / 'temp/binaries' / label / 'mariamem-host')]
subprocess.run(shared + ['--output', str(w / 'evidence/sharedhost'), '--scratch', str(w / 'temp/shared-scratch')], env=env, check=True)
subprocess.run(shared + ['--scales', 'small', '--plain-repeats', '30', '--resource-repeats', '30', '--output', str(w / 'evidence/small-repeat'), '--scratch', str(w / 'temp/repeat-scratch')], env=env, check=True)
assert len(json.loads((w/'evidence/matrix/inputs.json').read_text())['cells']) == 88
assert len(list((w/'evidence/sharedhost').glob('plain-*.json'))) == 36
assert len(list((w/'evidence/sharedhost').glob('resource-*.json'))) == 18
assert len(list((w/'evidence/small-repeat').glob('plain-*.json'))) == 60
assert len(list((w/'evidence/small-repeat').glob('resource-*.json'))) == 60
(w/'evidence/completion.json').write_text(json.dumps({'completed': True, 'executions': 262, 'runtime_sources': sources, 'harness_source_commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()},indent=2)+'\n')
print('PASS: all 262 executions accounted for; no runtime changes', flush=True)
