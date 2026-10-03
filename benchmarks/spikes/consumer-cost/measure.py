#!/usr/bin/env python3
"""Measure an actual released Go module in an external, replace-free consumer.

Run alone, or under the repository fan-out's exclusive measurement lock.
Build caches are cold, not the OS page cache. No production files are changed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import time
import zipfile
from collections import defaultdict

MAIN = r'''package main
import (
 "context"
 "database/sql"
 "fmt"
 "time"
 mariamem "github.com/masahitojp/mariamem"
 _ "github.com/go-sql-driver/mysql"
)
var marker = "original"
func smoke() error {
 ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second); defer cancel()
 server, err := mariamem.Start(ctx, mariamem.Options{}); if err != nil { return err }; defer server.Close()
 db, err := sql.Open("mysql", server.DSN()); if err != nil { return err }; defer db.Close()
 var one int
 if err = db.QueryRowContext(ctx, "SELECT 1").Scan(&one); err != nil { return err }
 if one != 1 { return fmt.Errorf("SELECT 1 = %d", one) }
 for _, q := range []string{"CREATE TABLE consumer_probe (id INT PRIMARY KEY, value VARCHAR(30)) ENGINE=InnoDB", "INSERT INTO consumer_probe VALUES (1, 'original')", "UPDATE consumer_probe SET value='changed' WHERE id=1"} {
  if _, err = db.ExecContext(ctx, q); err != nil { return err }
 }
 var value string
 if err = db.QueryRowContext(ctx, "SELECT value FROM consumer_probe WHERE id=1").Scan(&value); err != nil { return err }
 if value != "changed" { return fmt.Errorf("CRUD value = %q", value) }
 if _, err = db.ExecContext(ctx, "DELETE FROM consumer_probe WHERE id=1"); err != nil { return err }
 return server.Close()
}
func main() { if err := smoke(); err != nil { panic(err) }; fmt.Println("consumer OK", marker) }
'''
TEST = '''package main
import "testing"
func TestSmoke(t *testing.T) { t.Log(marker); if err := smoke(); err != nil { t.Fatal(err) } }
'''
CONTROL = '''package main
import ("database/sql"; "fmt"; _ "github.com/go-sql-driver/mysql")
func main() { db, err := sql.Open("mysql", "root@tcp(127.0.0.1:3306)/mysql"); if err != nil { panic(err) }; defer db.Close(); fmt.Println(db.Stats()) }
'''

def size(path):
    return sum(p.stat().st_size for p in path.rglob('*') if p.is_file()) if path.exists() else 0

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def disk_size(path):
    return int(subprocess.check_output(['du', '-sk', str(path)], text=True).split()[0])*1024 if path.exists() else 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', type=Path, required=True, help='new external directory, outside the checkout')
    ap.add_argument('--version', default='v0.4.0')
    args = ap.parse_args()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    consumer = work / 'consumer'; consumer.mkdir()
    module_cache = work / 'gomodcache'
    root = Path(subprocess.check_output(['go', 'env', 'GOROOT'], env={**os.environ, 'GOTOOLCHAIN': 'go1.26.8'}, text=True).strip())
    go = str(root / 'bin/go')
    base_env = {**os.environ, 'GOTOOLCHAIN': 'local', 'GOWORK': 'off', 'GOMODCACHE': str(module_cache)}
    for key in list(base_env):
        if key.startswith('MARIAMEM_'):
            del base_env[key]
    base_env.pop('GOFLAGS', None)
    result = {'schema': 1, 'source_tag': args.version, 'scenario': 'public-released-direct-link-consumer-v1',
              'harness_sha256': sha(Path(__file__).resolve()),
              'environment': {'system': platform.platform(), 'machine': platform.machine(), 'cpu_count': os.cpu_count(),
                              'go': subprocess.check_output([go, 'version'], env=base_env, text=True).strip(),
                              'go_env': json.loads(subprocess.check_output([go, 'env', '-json', 'GOOS', 'GOARCH', 'CGO_ENABLED', 'GOPROXY', 'GOSUMDB'], env=base_env, text=True))},
              'work': str(work), 'commands': []}

    def run(label, argv, cache='setup', cwd=consumer):
        env = {**base_env, 'GOCACHE': str(work / ('gocache-' + cache))}
        timefile = work / (label + '.time'); stdout = work / (label + '.stdout'); stderr = work / (label + '.stderr')
        start = time.monotonic()
        with stdout.open('w') as out, stderr.open('w') as err:
            process = subprocess.run(['/usr/bin/time', '-l', '-o', str(timefile), *argv], env=env, cwd=cwd, stdout=out, stderr=err)
        elapsed = time.monotonic()-start
        timing = timefile.read_text()
        match = re.search(r'([0-9.]+) real\s+([0-9.]+) user\s+([0-9.]+) sys', timing)
        rss = re.search(r'(\d+)\s+maximum resident set size', timing)
        row = {'label': label, 'argv': argv, 'cwd': str(cwd), 'cache': cache, 'returncode': process.returncode,
               'wall_seconds': elapsed, 'cpu_seconds': float(match[2])+float(match[3]) if match else None,
               'reported_max_rss_bytes': int(rss[1]) if rss else None,
               'build_cache_logical_bytes_after': size(Path(env['GOCACHE'])),
               'build_cache_allocated_bytes_after': disk_size(Path(env['GOCACHE'])),
               'stdout_sha256': sha(stdout), 'stderr_sha256': sha(stderr), 'time_sha256': sha(timefile)}
        result['commands'].append(row)
        (work/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(row), flush=True)
        if process.returncode:
            raise RuntimeError(f'{label} failed: {stderr.read_text()[-4000:]}')
        return stdout

    (consumer/'go.mod').write_text(f'module example.com/mariamem-consumer\n\ngo 1.26.0\n\nrequire (\n github.com/masahitojp/mariamem {args.version}\n github.com/go-sql-driver/mysql v1.9.3\n)\n')
    (consumer/'main.go').write_text(MAIN)
    (consumer/'main_test.go').write_text(TEST)
    downloaded = run('module-download', [go, 'mod', 'download', '-json', 'github.com/masahitojp/mariamem@'+args.version])
    module = json.loads(downloaded.read_text()); result['module'] = module
    source = Path(module['Dir']); zip_path = Path(module['Zip'])
    module_download_records = module_cache/'cache/download/github.com/masahitojp/mariamem'
    result['acquisition'] = {'zip_bytes': zip_path.stat().st_size, 'zip_sha256': sha(zip_path),
                             'extracted_logical_bytes': size(source),
                             'download_record_logical_bytes': size(module_download_records),
                             'mariamem_cache_logical_bytes': size(source)+size(module_download_records),
                             'mariamem_cache_allocated_bytes': disk_size(source)+disk_size(module_download_records),
                             'generated_go_logical_bytes': size(source/'internal/generatedgo'),
                             'encoded_image_logical_bytes': size(source/'internal/builtinruntime')}
    groups = defaultdict(lambda: {'uncompressed_bytes': 0, 'compressed_bytes': 0, 'files': 0})
    with zipfile.ZipFile(zip_path) as archive:
        for entry in archive.infolist():
            group = ('generated' if '/internal/generatedgo/' in entry.filename else
                     'encoded_image' if '/internal/builtinruntime/' in entry.filename else 'other')
            groups[group]['uncompressed_bytes'] += entry.file_size
            groups[group]['compressed_bytes'] += entry.compress_size
            groups[group]['files'] += 1
    result['zip_groups'] = dict(groups)
    run('dependencies-download', [go, 'mod', 'tidy'])
    result['acquisition']['complete_module_cache_logical_bytes'] = size(module_cache)
    result['acquisition']['complete_module_cache_allocated_bytes'] = disk_size(module_cache)
    result['consumer_source_sha256'] = {'main.go': sha(consumer/'main.go'), 'main_test.go': sha(consumer/'main_test.go'), 'go.mod': sha(consumer/'go.mod'), 'go.sum': sha(consumer/'go.sum')}
    for trial in (1, 2):
        cache = 'cold-build-'+str(trial)
        run('cold-build-'+str(trial), [go, 'build', '-o', str(work/f'consumer-{trial}'), '.'], cache)
        run('run-consumer-'+str(trial), [str(work/f'consumer-{trial}')], cache)
        if trial == 1:
            for repeat in (1, 2):
                run('warm-build-'+str(repeat), [go, 'build', '-o', str(work/'consumer-1'), '.'], cache)
    # Empty independent cache: first go test does not inherit the go build cache.
    cache = 'cold-test'
    run('cold-test', [go, 'test', './...'], cache)
    run('warm-test-cached', [go, 'test', './...'], cache)
    for repeat in (1, 2):
        run('warm-test-executed-'+str(repeat), [go, 'test', '-count=1', './...'], cache)
    run('post-test-build', [go, 'build', '-o', str(work/'consumer-test-cache'), '.'], cache)
    (consumer/'main.go').write_text(MAIN.replace('var marker = "original"', 'var marker = "consumer-only-change"'))
    run('consumer-change-build', [go, 'build', '-o', str(work/'consumer-test-cache'), '.'], cache)
    run('consumer-change-test', [go, 'test', './...'], cache)
    run('stripped-build', [go, 'build', '-ldflags=-s -w', '-o', str(work/'consumer-stripped'), '.'], cache)
    control = work/'driver-control'; control.mkdir()
    (control/'go.mod').write_text('module example.com/mysql-driver-control\n\ngo 1.26.0\n\nrequire github.com/go-sql-driver/mysql v1.9.3\n')
    (control/'main.go').write_text(CONTROL)
    run('control-tidy', [go, 'mod', 'tidy'], cache, control)
    run('control-build', [go, 'build', '-o', str(work/'control'), '.'], cache, control)
    run('control-stripped-build', [go, 'build', '-ldflags=-s -w', '-o', str(work/'control-stripped'), '.'], cache, control)
    result['binaries'] = {name: {'bytes': (work/name).stat().st_size, 'sha256': sha(work/name)} for name in ('consumer-1','consumer-stripped','control','control-stripped')}
    result['final_consumer_marker'] = 'consumer-only-change'
    result['notes'] = ['No replace, private GOPROXY, GOSUMDB override, -p setting, compiler workaround or generated-source edits.',
                       'OS page cache not flushed; cold means independent empty Go build cache.',
                       'macOS time -l max RSS is reported maximum process RSS, not aggregate simultaneously live compiler RSS.',
                       'CPU includes descendants; warm executed tests include actual Start/CRUD/Close.',
                       'The isolated workspace includes reproducible caches and binaries; it is not source evidence to commit.']
    (work/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Result: '+str(work/'result.json'), flush=True)

if __name__ == '__main__':
    main()
