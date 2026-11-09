"""Finite two-platform correctness check; not a performance/adoption campaign."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from git_identity import require_commit

p = argparse.ArgumentParser()
p.add_argument('--work', type=Path, required=True)
p.add_argument('--source-commit')
p.add_argument('--go-version', required=True)
a = p.parse_args()
w = a.work.resolve(); t = w / 'temp'; e = w / 'evidence'
for path in [t, e, t/'cache', t/'modcache', t/'gotmp', t/'scratch']:
    path.mkdir(parents=True, exist_ok=True)

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()

head = git('rev-parse', 'HEAD')
require_commit(ROOT, head)
assert head == (a.source_commit or os.environ.get('GITHUB_SHA') or head)
assert not git('status', '--porcelain')
assert (platform.system(), platform.machine()) in [('Darwin', 'arm64'), ('Linux', 'x86_64')]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

env = {k: v for k, v in os.environ.items() if not k.startswith(('GO', 'MARIAMEM_', 'MYSQLMEM_', 'STATIC_IMAGE_'))}
env.update(GOTOOLCHAIN='local', GOENV='off', GOWORK='off', CGO_ENABLED='0',
           GOCACHE=str(t/'cache'), GOMODCACHE=str(t/'modcache'), GOTMPDIR=str(t/'gotmp'),
           TMPDIR=str(t/'scratch'), GOMAXPROCS='4', GOGC='50', GOMEMLIMIT='3GiB')
go = subprocess.check_output(['go', 'version'], env=env, text=True).strip()
assert go.split()[2] == a.go_version
inputs = {'source_commit': head, 'go': go, 'platform': platform.platform(),
          'page_size': os.sysconf('SC_PAGE_SIZE'), 'binaries': {},
          'layout_sha256': sha(ROOT/'benchmarks/staticimage/layout.json'),
          'scope': 'layout regeneration and explicit-owner correctness; no performance or product adoption claim'}
(e/'inputs.json').write_text(json.dumps(inputs, indent=2)+'\n')

def run(name, cmd, cwd=ROOT, success=True, runenv=None):
    print(name, flush=True)
    with (e/(name+'.txt')).open('w') as log:
        result = subprocess.run(cmd, cwd=cwd, env=runenv or env, stdout=log, stderr=subprocess.STDOUT, timeout=600)
    assert (result.returncode == 0) == success, (name, result.returncode)
    return result.returncode

def bind(name):
    info = subprocess.check_output(['go', 'version', '-m', str(t/name)], env=env, text=True)
    assert 'vcs.revision='+head in info and 'vcs.modified=false' in info
    inputs['binaries'][name] = {'sha256': sha(t/name), 'build_info': info.replace(str(w), '<WORK>').replace(str(ROOT), '<SOURCE>')}
    (e/'inputs.json').write_text(json.dumps(inputs, indent=2)+'\n')

run('pure-layout', ['go', 'test', '-p', '1', '-count=1', '-v', './benchmarks/staticlayout'])
run('generator-build', ['go', 'build', '-p', '1', '-trimpath', '-buildvcs=true', '-o', str(t/'layoutgen'), './benchmarks/staticlayout/cmd'])
bind('layoutgen')
run('layout-check', [str(t/'layoutgen'), '-root', str(ROOT), '-output', str(ROOT/'benchmarks/staticimage/layout.json'), '-check'])
# Repeat generation is deterministic and does not edit the source or evidence.
run('layout-regenerate', [str(t/'layoutgen'), '-root', str(ROOT), '-output', str(t/'regenerated.json')])
assert (t/'regenerated.json').read_bytes() == (ROOT/'benchmarks/staticimage/layout.json').read_bytes()
original = json.loads((t/'regenerated.json').read_text())
for name in ['omit_flag', 'memory_hash', 'segment_state', 'source_hash']:
    value = json.loads(json.dumps(original))
    if name == 'omit_flag':
        value['end'] = (value['data_end']+4095)//4096*4096
    elif name == 'memory_hash':
        value['memory_sha256'] = '0'*64
    elif name == 'segment_state':
        value['dropped'][0] = not value['dropped'][0]
    else:
        value['source_sha256'][next(iter(value['source_sha256']))] = '0'*64
    path = t/(name+'.json'); path.write_text(json.dumps(value, indent=2)+'\n')
    run('negative-'+name, [str(t/'layoutgen'), '-root', str(ROOT), '-output', str(path), '-check'], success=False)
    assert 'layout differs:' in (e/('negative-'+name+'.txt')).read_text()
run('mapping-unit', ['go', 'test', '-p', '1', '-count=1', '-v', '-run', 'TestMapping|TestStaticPages', './internal/generatedgo/code/base'])
run('constructor-unit', ['go', 'test', '-p', '1', '-count=1', '-v', './benchmarks/staticimage'])
assert '--- SKIP' not in (e/'constructor-unit.txt').read_text()

probe = ROOT/'benchmarks/issue123baseline'
mod = t/'probe.mod'; mod.write_text((probe/'go.mod').read_text().replace('=> ../..', '=> '+str(ROOT)))
mod.with_suffix('.sum').write_bytes((probe/'go.sum').read_bytes())
run('probe-build', ['go', 'build', '-p', '1', '-trimpath', '-buildvcs=true', '-modfile', str(mod), '-mod=readonly', '-tags', 'issue123image', '-o', str(t/'probe'), './maria'], cwd=probe)
bind('probe')
records = []
for mode, parallel, negative in [('fresh',1,False), ('fork',1,False), ('fresh',4,False), ('fork',4,False), ('fresh',1,True), ('fork',1,True)]:
    name = f'{mode}-p{parallel}' + ('-negative' if negative else '')
    scratch = t/'scratch'/name; scratch.mkdir(exist_ok=True)
    assert not list(scratch.iterdir()), 'scratch is not empty before admission'
    v = dict(env, TMPDIR=str(scratch), MARIAMEM_STATIC_IMAGE_EXPERIMENT='1', GOGC='100')
    v.pop('GOMEMLIMIT')
    out = e/(name+'.json'); count = 1 if negative else 8
    cmd = [str(t/'probe'), '-mode', mode, '-parallel', str(parallel), '-count', str(count), '-out', str(out)]
    if negative:
        cmd += ['-corrupt-seed']
    rc = run(name, cmd, cwd=probe, success=not negative, runenv=v)
    report = json.loads(out.read_text()); im = report['image_stats']
    assert report['cleanup'] and not list(scratch.iterdir())
    assert report['mode'] == mode and report['parallel'] == parallel and report['count'] == count
    assert report['resolved_max_forks'] == (parallel if mode == 'fork' else 0)
    assert 0 < report['max_active'] <= parallel
    assert all(report['cleanup_stats'][k] == 0 for k in ['active_mappings', 'active_rw_bytes', 'active_reserved_bytes', 'release_failures'])
    assert im['enabled'] and im['closed'] and im['owned_fds'] == 0 and im['builds'] == 1 and im['page_only'] and not im['full_scan']
    assert 0 < im['scanned_bytes'] < original['memory_bytes'] and 0 < im['initialized_page_bytes'] < original['memory_bytes']
    if negative:
        assert rc == 1 and not report['success'] and 'pristine oracle' in report['error']
    else:
        assert report['success'] and len(report['samples']) == count
        assert {s['index'] for s in report['samples']} == set(range(count))
        assert all(s['oracle'] and s['cleanup'] and not s.get('error') for s in report['samples'])
        # The established probe records VERSION() on index0 in each process.
        assert '12.3.3' in next(s['version'] for s in report['samples'] if s['index'] == 0)
        assert im['acquires'] == count + (mode == 'fork')
    records.append({'case':name, 'expected_failure':negative, 'exit_code':rc, 'result':'PASS'})
assert not git('status', '--porcelain')
(e/'result.json').write_text(json.dumps({'result':'PASS', 'source_commit':head, 'cases':records,
    'layout_negative_controls':4, 'platform':platform.platform(), 'product_adoption':False}, indent=2)+'\n')
# Never publish runner-local paths in compact logs.
for path in e.glob('*.txt'):
    path.write_text(path.read_text().replace(str(w), '<WORK>').replace(str(ROOT), '<SOURCE>'))
(e/'SHA256SUMS.json').write_text(json.dumps({path.name:sha(path) for path in sorted(e.iterdir()) if path.is_file() and path.name!='SHA256SUMS.json'}, indent=2)+'\n')
print('PASS', head, flush=True)
