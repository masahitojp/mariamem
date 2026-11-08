"""Bounded both-host actual C guest acceptance. No performance or qualification claim."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
from common import digest
from git_identity import inspect_ref
from dev_guest import source_identity, inventory
from runtime_development_binding import profile, NAME, PROFILE_SHA256


def crc_test(source, relocations):
    # Test fixture only: exact tokens, never address matching in production adapters.
    return re.sub(r'(?<![\w])\d+\b', lambda m:str(relocations.get(m[0], m[0])), source)


def main():
    p = argparse.ArgumentParser(); p.add_argument('--acquired', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True); p.add_argument('--receipt', type=Path, required=True)
    a = p.parse_args(); a.receipt.mkdir(parents=True, exist_ok=False)
    git_identity = inspect_ref(ROOT, 'HEAD')
    identity = source_identity(ROOT)
    assert git_identity.object_type == 'commit' and git_identity.source_commit == identity['commit']
    assert identity['commit'] == os.environ['GITHUB_SHA']
    config = profile(ROOT, NAME)
    env = dict(os.environ, GOTOOLCHAIN='go1.26.10', GOWORK='off', GOENV='off', GOMAXPROCS='4', PYTHONDONTWRITEBYTECODE='1')
    commands = []
    def run(name, command, cwd=ROOT, extra=None, timeout=2400):
        with (a.receipt/(name+'.txt')).open('w') as log:
            result = subprocess.run(list(map(str, command)), cwd=cwd, env=dict(env, **(extra or {})), stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
        commands.append({'name':name, 'exit_code':result.returncode})
        if result.returncode:
            raise RuntimeError(name+' failed; see receipt log')
    result = {'result':'FAIL', 'contract':'development-unqualified-v1', 'host_source_commit':identity['commit'],
              'c_source_commit':config['source_commit'], 'guest_sha256':config['guest_sha256'],
              'binding_sha256':PROFILE_SHA256, 'platform':platform.platform(), 'machine':platform.machine(),
              'performance':'NOT_MEASURED', 'qualification':'NOT_RUN', 'adoption':'NOT_APPROVED'}
    try:
        run('regeneration', [sys.executable, ROOT/'scripts/regenerate_release_guest.py', '--development',
             '--development-binding', NAME, '--guest-dir', a.acquired/'guest', '--output', a.output], timeout=3600)
        product = a.output/'product'; runtime = product/'internal/generatedgo'
        development = json.loads((a.output/'development.json').read_text())
        assert development['guest_sha256'] == config['guest_sha256'] and development['smoke'] == 'PASS'
        assert development['host_source_identity'] == identity
        # No fixture mutation in the installed source tree. Go overlays name their exact target.
        tables = a.output/'lexer_prepared_candidate_test.go'
        shutil.copy2(ROOT/'benchmarks/lexercandidate/actual_guest_test.go.txt', tables)
        old = (product/'internal/generatedgo/code/p4/crc32c_test.go').read_text()
        crc = a.output/'crc32c_candidate_test.go'; crc.write_text(crc_test(old, config['crc_test_relocations']))
        overlay = a.output/'acceptance-overlay.json'
        overlay.write_text(json.dumps({'Replace':{str(runtime/'lexer_prepared_candidate_test.go'):str(tables),
                 str(runtime/'code/p4/crc32c_test.go'):str(crc)}}))
        result['test_overlay'] = {'sha256':digest(overlay), 'lexer_oracle_sha256':digest(tables),
                                 'crc_original_sha256':hashlib.sha256(old.encode()).hexdigest(), 'crc_relocated_sha256':digest(crc)}
        run('tables-corruption-worker', ['go','test','-p','1','-overlay',overlay,'-tags','integration','-count=1','-timeout','180s','-v',
            './internal/generatedgo','-run','^(TestPreparedLexerTablesActualGuest|TestWorkerTrapActualGuestNotifiesAndIsolatesPeer)$'], cwd=product)
        table_log = (a.receipt/'tables-corruption-worker.txt').read_text()
        for name in ('TestPreparedLexerTablesActualGuest/normal_ambient_ignored',
                     'TestPreparedLexerTablesActualGuest/profiling_does_not_verify',
                     'TestPreparedLexerTablesActualGuest/all_638_compiled_descriptors',
                     'TestPreparedLexerTablesActualGuest/corrupt_table_rejected',
                     'TestWorkerTrapActualGuestNotifiesAndIsolatesPeer'):
            assert '--- PASS: '+name+' ' in table_log, name
        run('crc-differential', ['go','test','-p','1','-overlay',overlay,'-count=1','-v','./internal/generatedgo/code/p4','-run','^TestCRC32C'], cwd=product)
        crc_log = (a.receipt/'crc-differential.txt').read_text()
        for name in ('TestCRC32CEquivalence', 'TestCRC32CPageValidation'):
            assert '--- PASS: '+name+' ' in crc_log, name
        run('join-ownership', [sys.executable, product/'tests/routine_thread_fixture.py','--development-binding',NAME,'--output',a.output/'join','--run'], cwd=product)
        join = json.loads((a.output/'join/results.json').read_text())
        assert len(join) == 6 and all(row['passed'] for row in join)
        shutil.copytree(a.output/'join', a.receipt/'join', ignore=shutil.ignore_patterns('module'))
        sql = a.receipt/'sql.json'
        run('sql-native-children-cleanup', [sys.executable, ROOT/'benchmarks/lexercandidate/sql_acceptance.py','--host',a.output/'mariamem-dev-host',
            '--native',a.acquired/'reference/native.json','--output',sql], extra={'PYTHONPATH':str(product/'python')})
        assert json.loads(sql.read_text())['result'] == 'PASS_GUEST'
        assert inventory(runtime) == development['generated_inventory']
        assert source_identity(ROOT) == identity
        shutil.copy2(a.output/'development.json', a.receipt/'development.json')
        shutil.copy2(a.output/'installation-inputs.json', a.receipt/'installation-inputs.json')
        shutil.copy2(a.acquired/'acquisition.json', a.receipt/'acquisition.json')
        result.update(result='PASS_ACTUAL_C_GUEST', host_sha256=digest(a.output/'mariamem-dev-host'))
    except BaseException as exc:
        result.update(exception=type(exc).__name__, message=str(exc))
        raise
    finally:
        result['commands'] = commands
        (a.receipt/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        (a.receipt/'SHA256SUMS.json').write_text(json.dumps(inventory(a.receipt), indent=2)+'\n')

if __name__ == '__main__': main()
