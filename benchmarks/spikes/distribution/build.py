"""Ordinary external-consumer builds/tests with isolated Go caches, no replace."""
import argparse, json, os, subprocess, time, resource, re
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument('--work', type=Path, required=True)
p.add_argument('--go', type=Path, required=True)
p.add_argument('--label', required=True)
p.add_argument('--fetch', action='store_true')
p.add_argument('--compat-only', action='store_true')
p.add_argument('--test-first', action='store_true')
a = p.parse_args()
work = a.work.resolve()
fixture = json.loads((work / 'fixtures.json').read_text())
consumer = Path(fixture['consumer'])
result = work / (a.label + '.json')
cache = work / (a.label + '-cache')
if cache.exists():
    raise RuntimeError('use a fresh label/cache')
env = dict(os.environ, GOENV='off', GOWORK='off', GOTOOLCHAIN='local', GOTELEMETRY='off', CGO_ENABLED='0', GOFLAGS='', GOEXPERIMENT='', GOCACHE=str(cache), GOMODCACHE=str(work / 'mod-cache'), GOPATH=str(work / 'gopath'), GOPROXY=fixture.get('proxy', (work / 'proxy').as_uri()), GOSUMDB=fixture.get('sumdb', 'off'))
for k in ('MARIAMEM_NATIVE_DIR', 'MARIAMEM_RUNTIME'):
    env.pop(k, None)
rows = []
data = {'label': a.label, 'go_version': subprocess.check_output([str(a.go.resolve()), 'version'], text=True).strip(), 'samples': rows, 'consumer_path': str(consumer), 'replace': False}

def run(name, args):
    begin = time.monotonic()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    r = subprocess.run(['/usr/bin/time', '-l', str(a.go.resolve()), *args], cwd=consumer, env=env, capture_output=True, text=True)
    elapsed = time.monotonic() - begin
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    log = work / (a.label + '-' + name + '.log')
    log.write_text(r.stdout + '\n' + r.stderr)
    rss = re.search('(\\d+)\\s+maximum resident set size', r.stderr)
    row = {'phase': name, 'wall_sec': elapsed, 'cpu_sec': after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime, 'reported_max_rss_bytes': int(rss.group(1)) if rss else None, 'exit_code': r.returncode, 'stdout': r.stdout[-3000:], 'stderr_tail': r.stderr[-4500:] if r.returncode else None}
    rows.append(row)
    result.write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps(row), flush=True)
    return r.returncode
if a.fetch and run('module_fetch', ['mod', 'download', '-json', fixture.get('module', 'github.com/masahitojp/mariamem') + '@' + fixture['tag']]):
    raise SystemExit(1)
binary = work / (a.label + '-app')
build = ['build', '-mod=mod', '-o', str(binary), '.']
if a.test_first and run('clean_ci_test', ['test', '-mod=mod', '-v', './...']):
    raise SystemExit(1)
if run('build_after_ci_test' if a.test_first else 'cold_build', build):
    raise SystemExit(1)
if a.compat_only:
    raise SystemExit(0)
for name, args in [('cold_test', ['test', '-mod=mod', '-v', './...']), ('warm_build_1', build), ('warm_build_2', build), ('warm_test', ['test', '-v', './...']), ('warm_test_uncached', ['test', '-v', '-count=1', './...'])]:
    if run(name, args):
        raise SystemExit(1)
main = consumer / 'main.go'
original = main.read_text()
main.write_text(original.replace('original', 'consumer-edit', 1))
try:
    if run('consumer_edit_build', build) or run('consumer_edit_test', ['test', '-v', './...']):
        raise SystemExit(1)
finally:
    main.write_text(original)
if run('stripped_build', ['build', '-ldflags=-s -w', '-o', str(work / (a.label + '-stripped')), '.']):
    raise SystemExit(1)
if run('test_binary', ['test', '-c', '-o', str(work / (a.label + '-test')), '.']):
    raise SystemExit(1)
data.update(app_bytes=binary.stat().st_size, stripped_app_bytes=(work / (a.label + '-stripped')).stat().st_size, test_binary_bytes=(work / (a.label + '-test')).stat().st_size, mod_cache_bytes=sum((x.stat().st_size for x in (work / 'mod-cache').rglob('*') if x.is_file())), build_cache_bytes=sum((x.stat().st_size for x in cache.rglob('*') if x.is_file())))
result.write_text(json.dumps(data, indent=2) + '\n')
print(json.dumps({k: v for k, v in data.items() if k not in ('samples', 'consumer_path')}))
