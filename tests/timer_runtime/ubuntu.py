"""Bounded Ubuntu/native confirmation of the retained timer candidate.

The orchestration commit is separate from the immutable host/guest sources.
This does not qualify a release or measure a before/after performance change.
"""
import argparse
from dataclasses import asdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from git_identity import inspect_ref, require_commit

HOST = 'f225968c332a692f5bce189b31aed1fab26e642a'
GUEST_SOURCE = '1731c394031b781ff813190bf9c42bee63516044'
GUEST = 'a64b581154d7d1ca2ca8aae9a552c9433f7f1354b7c7f5a36d600b62a32d2c18'
ARTIFACT = 13814809081
RUN = 42928025946
ARCHIVE = '2f99c67b79caae6a7cc8bee87fc820f3bebd783efb1c26a4e46d3bec9d556342'
API = 'repos/masahitojp/mariamem/actions'


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def check_artifact(meta, archive_digest):
    need(meta['id'] == ARTIFACT and not meta['expired'], 'artifact ID/expiry')
    need(meta['workflow_run']['id'] == RUN and
         meta['workflow_run']['head_sha'] == GUEST_SOURCE, 'artifact source/run')
    need(meta['digest'] == 'sha256:' + ARCHIVE and archive_digest == ARCHIVE,
         'artifact archive digest')


def semantic_rows(record):
    need(record['result'] == 'PASS', 'SQL oracle failed')
    rows = record['observations']
    need(len(rows) == 18, 'SQL observation count')
    profile = [(phase, pair, delayed) for phase in ('fresh', 'child1', 'child2')
               for pair in range(3) for delayed in (False, True)]
    need([(r['phase'], r['pair'], r['delayed']) for r in rows] == profile,
         'SQL phase/pair profile')
    result = []
    for row in rows:
        block = row['report']['query_block']
        table = block['nested_loop'][0]['table']
        need(table['r_rows'] == 2 and table['r_loops'] == 1 and
             row['subsequent_select'] == 'PASS', 'SQL row/loop/following SELECT')
        if row['delayed']:
            total = block.get('r_total_time_ms')
            need(isinstance(total, (int, float)) and 18 <= total <= row['wall_ms'] + 5,
                 'delayed query timing')
        result.append((row['phase'], row['pair'], row['delayed'], row['sql'],
                       table['r_rows'], table['r_loops'], row['subsequent_select']))
    return result


def check_pipe(record):
    need(record['subsequent_select'] == 'PASS' and record['active_mappings_after'] == 0,
         'Pipe following SELECT/cleanup')
    rows = record['rows']
    need([(r['repeat'], r['delay']) for r in rows] ==
         [(pair, delay) for pair in range(3) for delay in (False, True)], 'Pipe pair profile')
    for row in rows:
        need('error' not in row, 'Pipe SQL error')
        block = json.loads(row['raw'])['query_block']
        table = block['nested_loop'][0]['table']
        need(table['r_rows'] == 2 and table['r_loops'] == 1, 'Pipe row/loop')
        if row['delay']:
            total = block.get('r_total_time_ms')
            need(isinstance(total, (int, float)) and 18 <= total <= row['wall_ms'] + 5,
                 'Pipe delayed query timing')


def native_oracle(host_source, port, output):
    # Reuse exactly the SQL and reporting assertions used by the guest oracle.
    sys.path.insert(0, str(host_source / 'python'))
    spec = importlib.util.spec_from_file_location(
        'timer_sql_oracle', host_source / 'tests/timer_runtime/oracle.py')
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    import pymysql

    schema = 'mariamem_timer_native_probe'
    config = dict(host='127.0.0.1', port=port, user='root')

    class Native:
        def connection_info(self):
            return dict(config, database=schema)

        def wait_disconnected(self):
            pass  # PyMySQL connection contexts above have closed.

    result = dict(result='FAIL', observations=[], scope='native SQL only; no native Snapshot')
    with pymysql.connect(**config, autocommit=True) as conn, conn.cursor() as q:
        q.execute('SELECT VERSION(), @@version_compile_machine')
        result['server'] = list(q.fetchone())
        need(result['server'] == ['12.3.3-MariaDB-ubu2404', 'x86_64'], 'native server identity')
        q.execute('SELECT COUNT(*) FROM information_schema.schemata WHERE SCHEMA_NAME=%s', (schema,))
        need(q.fetchone() == (0,), 'native schema already present')
        q.execute('CREATE DATABASE ' + schema)
        try:
            # Independently recreate the same two rows for each profile phase;
            # this is a SQL reference, not an emulation of Snapshot semantics.
            for phase in ('fresh', 'child1', 'child2'):
                q.execute('CREATE OR REPLACE TABLE ' + schema + '.timer_probe(id INT PRIMARY KEY) ENGINE=InnoDB')
                q.execute('INSERT INTO ' + schema + '.timer_probe VALUES(1),(2)')
                oracle.measure(Native(), phase, result['observations'])
            result['result'] = 'PASS'
        finally:
            q.execute('DROP DATABASE ' + schema)
            q.execute('SELECT COUNT(*) FROM information_schema.schemata WHERE SCHEMA_NAME=%s', (schema,))
            result['schema_count_after'] = q.fetchone()[0]
            need(result['schema_count_after'] == 0, 'native cleanup')
            write(output, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--native-container', required=True)
    parser.add_argument('--port', type=int, default=3307)
    args = parser.parse_args()
    work, out = args.work.resolve(), args.output.resolve()
    need(not work.exists() and not out.exists(), 'fresh work/output required')
    need(not work.is_relative_to(ROOT) and not out.is_relative_to(ROOT), 'use external scratch')
    work.mkdir(parents=True)
    out.mkdir(parents=True)
    require_commit(ROOT, args.source_commit)
    identity = asdict(inspect_ref(ROOT, 'HEAD'))
    need(identity['source_commit'] == args.source_commit, 'orchestration source mismatch')
    need(not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT).strip(), 'dirty source')
    need(platform.system() == 'Linux' and platform.machine() == 'x86_64', 'Ubuntu x86_64 only')
    write(out / 'source.json', identity)
    result = dict(result='FAIL', qualification=False, source_commit=args.source_commit,
                  host_source_commit=HOST, guest_source_commit=GUEST_SOURCE, guest_sha256=GUEST,
                  platform=platform.platform(), performance_comparison=False)
    env = dict(os.environ, GOTOOLCHAIN='go1.26.10', GOWORK='off', GOENV='off',
               GOFLAGS='', GOEXPERIMENT='', GOCACHE=str(work / 'gocache'),
               GOPATH=str(work / 'gopath'), GOMODCACHE=str(work / 'modcache'),
               GOMAXPROCS='8', GOGC='100', SHOP_PARALLEL='4', ISSUE88_POOL_MIB='16',
               FORK_STAGES='0', TIMER_ANALYZE_PROBE='0', TIMER_LIFECYCLE='0')
    env.pop('MARIAMEM_DEV_WORKSPACE', None)

    def run(argv, label, cwd=ROOT, extra=None, timeout=2400):
        with (out / (label + '.log')).open('w') as log:
            subprocess.run(list(map(str, argv)), cwd=cwd, env=dict(env, **(extra or {})),
                           stdout=log, stderr=subprocess.STDOUT, check=True, timeout=timeout)

    try:
        host = work / 'host-source'
        require_commit(ROOT, HOST)
        run(['git', 'worktree', 'add', '--detach', host, HOST], 'host-checkout')
        run([sys.executable, ROOT / 'tests/dump_import_acceptance/linux_acquisition.py',
             '--container', args.native_container, '--expected-source-commit', args.source_commit,
             '--output', out / 'native-acquisition'], 'native-acquisition')
        meta = json.loads(subprocess.check_output(['gh', 'api', API + '/artifacts/' + str(ARTIFACT)]))
        archive = work / 'guest.zip'
        with archive.open('wb') as f:
            subprocess.run(['gh', 'api', API + '/artifacts/' + str(ARTIFACT) + '/zip'], stdout=f, check=True)
        check_artifact(meta, sha(archive))
        write(out / 'artifact.json', meta)
        guest = work / 'guest'
        with zipfile.ZipFile(archive) as z:
            need(all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in z.namelist()),
                 'unsafe archive path')
            z.extractall(guest)
        need(sha(guest / 'mariamem.wasm') == GUEST, 'guest bytes')
        runtime = work / 'runtime'
        run([sys.executable, host / 'scripts/regenerate_release_guest.py', '--development',
             '--guest-dir', guest, '--output', runtime], 'regeneration', cwd=host)
        receipt = json.loads((runtime / 'development.json').read_text())
        need(receipt['smoke'] == 'PASS' and receipt['guest_sha256'] == GUEST and
             receipt['host_source_identity']['commit'] == HOST and
             receipt['source_identity']['commit'] == GUEST_SOURCE, 'regeneration identity/smoke')
        # Full inventories remain in CI evidence, never source-controlled as raw output.
        (out / 'development.json').write_bytes((runtime / 'development.json').read_bytes())
        run([sys.executable, host / 'tests/timer_runtime/oracle.py', '--host',
             runtime / 'mariamem-dev-host', '--output', out / 'guest-sql.json'], 'guest-sql',
            cwd=host, extra={'PYTHONPATH': str(runtime / 'product/python')}, timeout=180)
        native = native_oracle(host, args.port, out / 'native-sql.json')
        guest_sql = json.loads((out / 'guest-sql.json').read_text())
        need(semantic_rows(guest_sql) == semantic_rows(native), 'native/guest SQL semantics')
        runner = runtime / 'product/tests/timer_calibration/runner'
        binary = work / 'pipe.test'
        run(['go', 'test', '-mod=readonly', '-p', '1', '-trimpath', '-buildvcs=false',
             '-c', '-o', binary, './maria/store'], 'pipe-build', cwd=runner)
        run([binary, '-test.timeout=180s'], 'pipe-sql', cwd=runner,
            extra={'TIMER_ANALYZE_PROBE': '1', 'ANALYZE_PROBE_PATH': str(out / 'pipe-sql.json')},
            timeout=210)
        pipe = json.loads((out / 'pipe-sql.json').read_text())
        check_pipe(pipe)
        run([binary, '-test.timeout=180s'], 'lifecycle', cwd=runner,
            extra={'TIMER_LIFECYCLE': '1', 'MODELCASE_TRACE': str(out / 'lifecycle.json')},
            timeout=210)
        lifecycle = json.loads((out / 'lifecycle.json').read_text())
        need(lifecycle['result'] == 'PASS' and lifecycle['active_mappings_after'] == 0 and
             len(lifecycle['observations']) == 24, 'lifecycle/cleanup')
        result.update(result='PASS', sql_comparison='PASS', pipe_sql='PASS',
                      lifecycle='PASS', binary_sha256=receipt['binary_sha256'],
                      pipe_binary_sha256=sha(binary), native_schema_count_after=0)
    except BaseException as exc:
        result['error'] = type(exc).__name__ + ': ' + str(exc)
        raise
    finally:
        write(out / 'assessment.json', result)
        write(out / 'SHA256SUMS.json', {str(p.relative_to(out)): sha(p)
              for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'SHA256SUMS.json'})


if __name__ == '__main__':
    main()
