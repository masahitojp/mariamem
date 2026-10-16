"""Two-pair heap-allocation attribution investigation; never modify runtime or its oracle."""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--go-root', type=Path, required=True)
    a = p.parse_args()
    w = a.workspace.resolve()
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / 'scripts'))
    from experiment_disk import DiskGuard, run_guarded
    from git_identity import read_release_pin, require_commit, verify_go_binary, verify_release_pin
    env = {k: v for k, v in os.environ.items() if not k.startswith(('MARIAMEM_', 'MYSQLMEM_'))}
    for key in ['GOMAXPROCS', 'GOMEMLIMIT', 'GOGC']:
        env.pop(key, None)
    env.update(GOTOOLCHAIN='local', CGO_ENABLED='0', PATH=str(a.go_root / 'bin') + os.pathsep + env['PATH'])
    for key, name in [('GOCACHE', 'go-cache'), ('GOMODCACHE', 'go-mod'), ('GOPATH', 'go-path'), ('GOTMPDIR', 'go-tmp')]:
        env[key] = str(w / 'temp' / name)
        Path(env[key]).mkdir(exist_ok=True)
    go = a.go_root / 'bin/go'
    assert subprocess.check_output([go, 'version'], env=env, text=True).strip() == 'go version go1.26.8 darwin/arm64'
    sources = {'baseline': '44100ec676c8c9064f32f3a01bd9a990d487bb61',
               'candidate': '7a82f338cf111d5d52538b5a3f7bf129c12e2dbb'}
    receipt = dict(completed=False, started=time.time(), sources={}, cells=[],
        harness_source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        runner_sha256=digest(Path(__file__)), host=subprocess.check_output(['uname', '-a'], text=True).strip(),
        go='go1.26.8', cgo_enabled=0, flags=['-p', '1', '-trimpath', '-buildvcs=true'])

    def save():
        (w / 'evidence/receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')

    guard = DiskGuard(w, 20, 8)
    for label, sha in sources.items():
        checkout = w / 'temp' / label
        if not checkout.exists():
            subprocess.run(['git', 'clone', '--quiet', '--no-hardlinks', '--no-checkout', str(root), str(checkout)], check=True)
        subprocess.run(['git', 'checkout', '--quiet', '--detach', sha], cwd=checkout, check=True)
    helper = w / 'temp/process-cost'
    subprocess.run(['cc', '-O2', str(root / 'benchmarks/tools/process_cost.c'), '-o', str(helper)], check=True)
    receipt['process_helper_sha256'] = digest(helper)
    for label, sha in sources.items():
        checkout = w / 'temp' / label
        tag = 'v0.5.0' if label == 'baseline' else 'v0.5.1'
        pin = read_release_pin(root / 'release/baselines' / (tag + '.json'))
        verify_release_pin(root, pin)
        assert pin.source_commit == sha
        require_commit(checkout, sha)
        assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=checkout, text=True).strip() == sha
        assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=checkout)
        source = checkout / 'benchmarks/ownedprepared/main.go'
        before = source.read_text()
        after = before.replace('\t"runtime"\n', '\t"runtime"\n\t"runtime/pprof"\n')
        assert after != before
        after = after.replace('\tflag.Parse()\n', '\tprofilePath := flag.String("diagnostic-cpu-profile", "", "observer only: optional CPU profile")\n\tflag.Parse()\n\tif *profilePath != "" {\n\t\tf, e := os.Create(*profilePath); must(e)\n\t\tmust(pprof.StartCPUProfile(f))\n\t\tdefer func() { pprof.StopCPUProfile(); must(f.Close()) }()\n\t}\n')
        # Observer work stays outside existing product timing; no extra GC or sampling-rate change.
        after = after.replace('\tflag.Parse()\n', '\tallocPath := flag.String("diagnostic-alloc-profile", "", "observer only: default-rate cumulative alloc profile")\n\tflag.Parse()\n\tif *allocPath != "" { defer func() { f,e:=os.Create(*allocPath); must(e); must(pprof.Lookup("allocs").WriteTo(f,0)); must(f.Close()) }() }\n')
        after = after.replace('\t\tt, c := time.Now(), cpu()\n', '\t\tbeforeHeap := goResourcePoint()\n\t\tt, c := time.Now(), cpu()\n')
        after = after.replace('\t\tvar cpuValue any = consumed\n', '\t\tafterHeap := goResourcePoint()\n\t\tvar cpuValue any = consumed\n')
        after = after.replace('"cpu_seconds": cpuValue}', '"cpu_seconds": cpuValue, "heap_before": beforeHeap, "heap_after": afterHeap}')
        assert after.count('beforeHeap :=') == 1 and after.count('heap_before') == 1
        resources = checkout / 'benchmarks/ownedprepared/resources.go'
        rs = resources.read_text().replace('\treturn map[string]any{"heap_alloc_bytes":', '\ts := []metrics.Sample{{Name: "/gc/heap/allocs-by-size:bytes"}}\n\tmetrics.Read(s)\n\th := s[0].Value.Float64Histogram()\n\tbounds := make([]string,len(h.Buckets)); for i,v := range h.Buckets { bounds[i]=fmt.Sprint(v) }\n\treturn map[string]any{"allocation_size_counts": append([]uint64(nil),h.Counts...), "allocation_size_bounds": bounds, "heap_alloc_bytes":').replace('import (\n', 'import (\n\t"fmt"\n')
        resource_overlay = w / 'temp' / (label + '-resources.go')
        resource_overlay.write_text(rs)
        (w / 'evidence' / (label + '-observer.go.txt')).write_text(after)
        (w / 'evidence' / (label + '-resources.go.txt')).write_text(rs)
        assert after.count('StartCPUProfile') == 1 and after.count('diagnostic-cpu-profile') == 1
        overlay_source = w / 'temp' / (label + '-observer.go')
        overlay_source.write_text(after)
        overlay = w / 'temp' / (label + '-overlay.json')
        overlay.write_text(json.dumps({'Replace': {str(source): str(overlay_source), str(resources): str(resource_overlay)}}) + '\n')
        row = dict(identity=asdict(require_commit(checkout, sha)), tag_object_sha=pin.tag_object_sha,
                   benchmark_source_sha256=digest(source), observer_source_sha256=digest(overlay_source),
                   overlay_sha256=digest(overlay), resource_source_sha256=digest(resources), resource_observer_sha256=digest(resource_overlay), binaries={})
        for kind in ['observer']:
            binary = w / 'temp' / (label + '-' + kind)
            command = [str(go), 'build', '-p', '1', '-trimpath', '-buildvcs=true']
            if kind == 'observer':
                command += ['-overlay', str(overlay)]
            command += ['-o', str(binary), './benchmarks/ownedprepared']
            print('BUILD', label, kind, flush=True)
            subprocess.run(command, cwd=checkout, env=env, check=True)
            row['binaries'][kind] = dict(sha256=digest(binary),
                build_info=verify_go_binary(checkout, binary, sha, go=go))
        receipt['sources'][label] = row
        save()

    def execute(label, kind, trial, profiled):
        name = f'{kind}-{trial}-{label}-' + ('cpu' if profiled else 'plain')
        dest = w / 'evidence' / (name + '.json')
        binary = w / 'temp' / (label + '-' + kind)
        command = [str(binary), '-payload-mib', '100', '-tables', '8', '-workers', '1',
                   '-forks', '4', '-workload', 'app-connections', '-lifecycle', 'fresh',
                   '-go-resources', '-helper', str(helper), '-label', sources[label], '-out', str(dest)]
        profile = w / 'evidence' / (name + '.pprof')
        if profiled:
            command += ['-diagnostic-cpu-profile', str(profile), '-diagnostic-alloc-profile', str(profile.with_name(profile.stem + '-allocs.pprof'))]
        print('RUN', name, flush=True)
        with dest.with_suffix('.txt').open('w') as log:
            code = run_guarded(command, guard, cwd=w / 'temp' / label, env=env, output=log, timeout=180, interval=5)
        row = dict(name=name, label=label, kind=kind, trial=trial, profiled=profiled, returncode=code)
        receipt['cells'].append(row)
        save()
        if code:
            raise SystemExit(f'Original oracle failed: {name} ({code}); incomplete')
        d = json.loads(dest.read_text())
        m = d['resources']['after_go']['linear_memory_virtual']
        assert m['creates'] == m['releases'] == 4
        assert m['active_mappings'] == m['active_reserved_bytes'] == m['active_rw_bytes'] == m['release_failures'] == 0
        assert d['go_resource_observation']['process_peak_rss_bytes'] <= 8 * 1024**3
        row.update(product_seconds=d['suite_product_seconds'], cpu_seconds=d['suite_cpu_seconds'],
                   result_sha256=digest(dest))
        if profiled:
            row['profile_sha256'] = digest(profile)
            for report, args in [('top', ['-top', '-nodecount=45']),
                                 ('cum', ['-top', '-cum', '-nodecount=45']),
                                 ('raw', ['-raw']),
                                 ('storage', ['-top', '-nodecount=45', '-focus=blockStorage|memFile|MemFS']),
                                 ('gc', ['-top', '-nodecount=30', '-focus=runtime.gc|runtime.scan|runtime.malloc'])]:
                output = subprocess.check_output([go, 'tool', 'pprof', *args, binary, profile], env=env, stderr=subprocess.STDOUT)
                (w / 'evidence' / (name + '-' + report + '.txt')).write_bytes(output)
        if profiled:
            ap = profile.with_name(profile.stem + '-allocs.pprof')
            row['alloc_profile_sha256'] = digest(ap)
            for report, args in [('raw', ['-raw']), ('space', ['-top', '-sample_index=alloc_space', '-nodecount=80']), ('objects', ['-top', '-sample_index=alloc_objects', '-nodecount=80'])]:
                output = subprocess.check_output([go, 'tool', 'pprof', *args, binary, ap], env=env, stderr=subprocess.STDOUT)
                (w / 'evidence' / (name + '-allocs-' + report + '.txt')).write_bytes(output)
        save()
        print('PASS', name, round(row['product_seconds'], 3), round(row['cpu_seconds'], 3), flush=True)

    for trial in range(2):
        order = ['baseline', 'candidate'] if trial == 0 else ['candidate', 'baseline']
        for label in order:
            execute(label, 'observer', trial, True)
    assert len(receipt['cells']) == 4
    for label, sha in sources.items():
        checkout = w / 'temp' / label
        assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=checkout)
        for kind in ['observer']:
            assert digest(w / 'temp' / (label + '-' + kind)) == receipt['sources'][label]['binaries'][kind]['sha256']
    receipt.update(completed=True, ended=time.time(), peak_owned_bytes=guard.peak, minimum_free_bytes=guard.minimum_free)
    save()
    print('PASS: 4 executions, runtime inputs unchanged, original SQL/cleanup oracles intact', flush=True)


if __name__ == '__main__':
    main()
