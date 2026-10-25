"""Native identity and TCP producer probe; no application dump or import."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import re
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PIN = Path(__file__).with_name('linux-native-pin.json')
sys.path.insert(0, str(ROOT/'scripts'))
from git_identity import inspect_ref, require_commit

PROBE_DATABASE = 'mariamem_acquisition_probe'
TCP_ROOT = ['--no-defaults', '--protocol=tcp', '--host=127.0.0.1', '--port=3306',
            '--user=root', '--default-character-set=utf8mb4', '--batch', '--raw',
            '--skip-column-names']
DUMP_OPTIONS = ['--no-defaults', '--protocol=tcp', '--host=127.0.0.1', '--port=3306',
                '--user=root', '--opt', '--single-transaction', '--skip-lock-tables',
                '--skip-add-locks', '--routines', '--triggers', '--skip-events', '--hex-blob',
                '--default-character-set=utf8mb4', '--tz-utc', '--order-by-primary',
                '--skip-dump-date']
ROUTINE_METADATA = ('probe_function\tFUNCTION\troot@localhost\tDEFINER\n'
                    'probe_procedure\tPROCEDURE\troot@localhost\tDEFINER\n')


def require(condition, reason):
    # Do not use Python assert: python -O must not turn off input guards.
    if not condition:
        raise ValueError(reason)


def architecture(binary):
    require(len(binary) >= 20 and binary[:4] == b'\x7fELF', 'not an ELF executable')
    require(binary[4] in (1, 2) and binary[5] in (1, 2), 'invalid ELF encoding')
    order = '<' if binary[5] == 1 else '>'
    return {'format': 'ELF', 'bits': {1: 32, 2: 64}[binary[4]],
            'byte_order': 'little' if binary[5] == 1 else 'big',
            'machine': struct.unpack_from(order+'H', binary, 18)[0]}


def source_identity(expected):
    require_commit(ROOT, expected)
    actual = asdict(inspect_ref(ROOT, 'HEAD'))
    require(actual['object_type'] == 'commit' and actual['source_commit'] == expected,
            'checkout source_commit differs from requested source SHA')
    require(not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip(),
            'checkout is dirty')
    return actual


def validate(observed, pin, expected_source):
    require(isinstance(expected_source, str) and re.fullmatch('[0-9a-f]{40}', expected_source),
            'expected source must be a full commit SHA')
    source = observed.get('source', {})
    require(source.get('object_type') == 'commit' and
            source.get('object_sha') == source.get('source_commit') == expected_source,
            'source identity mismatch')
    for key in ['host', 'image_ref', 'image', 'startup_query']:
        require(observed.get(key) == pin[key], key+' mismatch')
    require(observed.get('container_image') == pin['image']['id'], 'container image mismatch')
    programs = observed.get('programs', {})
    require(set(programs) == set(pin['programs']), 'program inventory mismatch')
    for name, expected in pin['programs'].items():
        require(programs[name] == expected, name+' identity mismatch')


def producer_probe(container, command, output):
    """Exercise only the selected native producer connection/definer boundary."""
    client = ['docker', 'exec', container, 'mariadb', *TCP_ROOT]
    probe = {'result': 'FAIL', 'database': PROBE_DATABASE, 'commands': [],
             'application_dump_generated': False, 'dump_imported': False}
    count_sql = ("SELECT COUNT(*) FROM information_schema.schemata "
                 "WHERE SCHEMA_NAME='"+PROBE_DATABASE+"';")
    def query(label, sql):
        argv = [*client, '--execute='+sql]
        probe['commands'].append(argv)
        raw = command(argv)
        (output/(label+'.txt')).write_bytes(raw)
        return raw.decode()
    try:
        login = query('tcp-root-login', 'SELECT USER(), CURRENT_USER();')
        accounts = login.strip().split('\t')
        require(len(accounts) == 2 and all(a.split('@', 1)[0] == 'root' for a in accounts),
                'TCP login did not authenticate as root')
        # TCP authentication can select root@%; the routine definer is fixed
        # separately and must be checked through metadata and execution.
        probe['tcp_login'] = accounts
        require(query('probe-absent-before', count_sql) == '0\n', 'probe schema already exists')
        try:
            query('create-definer-routines',
                'CREATE DATABASE '+PROBE_DATABASE+' CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; '
                "CREATE DEFINER='root'@'localhost' PROCEDURE "+PROBE_DATABASE+'.probe_procedure() '
                'SQL SECURITY DEFINER SELECT 17; '
                "CREATE DEFINER='root'@'localhost' FUNCTION "+PROBE_DATABASE+'.probe_function() '
                'RETURNS INT DETERMINISTIC NO SQL SQL SECURITY DEFINER RETURN 19;')
            metadata = query('tcp-routine-metadata',
                'SELECT ROUTINE_NAME,ROUTINE_TYPE,DEFINER,SECURITY_TYPE '
                "FROM information_schema.routines WHERE ROUTINE_SCHEMA='"+PROBE_DATABASE+"' ORDER BY ROUTINE_NAME;")
            require(metadata == ROUTINE_METADATA, 'TCP routine DEFINER/SQL SECURITY mismatch')
            probe['routine_metadata'] = metadata
            calls = query('tcp-routine-results', 'CALL '+PROBE_DATABASE+'.probe_procedure(); '
                          'SELECT '+PROBE_DATABASE+'.probe_function();')
            require(calls == '17\n19\n', 'TCP definer routine execution mismatch')
            probe['routine_results'] = calls
            argv = ['docker', 'exec', container, 'mariadb-dump', *DUMP_OPTIONS, PROBE_DATABASE]
            probe['dump_argv'] = argv
            probe['commands'].append(argv)
            raw = command(argv)
            (output/'producer-probe.sql').write_bytes(raw)
            for kind, name in [('FUNCTION', 'probe_function'), ('PROCEDURE', 'probe_procedure')]:
                marker = ('CREATE DEFINER=`root`@`localhost` '+kind+' `'+name+'`').encode()
                require(marker in raw, 'TCP mariadb-dump omitted selected definer '+kind)
            probe['diagnostic_dump_sha256'] = hashlib.sha256(raw).hexdigest()
            probe['diagnostic_dump_bytes'] = len(raw)
        finally:
            query('drop-probe-schema', 'DROP DATABASE IF EXISTS '+PROBE_DATABASE+';')
            probe['schema_count_after'] = query('probe-absent-after', count_sql)
            require(probe['schema_count_after'] == '0\n', 'producer probe cleanup failed')
        probe['result'] = 'PASS'
        return probe
    except subprocess.CalledProcessError as error:
        (output/'producer-probe.stderr.txt').write_bytes(error.stderr or b'')
        raise
    finally:
        (output/'producer-probe.json').write_text(json.dumps(probe, indent=2)+'\n')


def capture(container, expected_source, pin, output):
    observed = {'source': source_identity(expected_source),
                'host': {'system': platform.system(), 'machine': platform.machine()},
                'image_ref': pin['image_ref'], 'programs': {}}
    # Resolve source before spending work on container/executable inspection.
    def command(arguments):
        result = subprocess.run(arguments, capture_output=True, check=True, timeout=45)
        return result.stdout
    image_raw = command(['docker', 'image', 'inspect', pin['image_ref']])
    container_raw = command(['docker', 'inspect', container])
    (output/'image.json').write_bytes(image_raw)
    (output/'container.json').write_bytes(container_raw)
    image = json.loads(image_raw)[0]
    require(pin['image_ref'] in image['RepoDigests'], 'inspected image does not bind pinned manifest')
    observed['image'] = {'id': image['Id'], 'os': image['Os'], 'architecture': image['Architecture']}
    observed['container_image'] = json.loads(container_raw)[0]['Image']
    for name, expected in pin['programs'].items():
        resolved = command(['docker', 'exec', container, 'sh', '-ec', 'command -v "$1"', 'sh', name]).decode().strip()
        require(resolved == expected['path'], name+' PATH resolves to another executable')
        binary = command(['docker', 'exec', container, 'cat', resolved])
        version = command(['docker', 'exec', container, name, '--no-defaults', '--version'])
        (output/(name+'-version.txt')).write_bytes(version)
        observed['programs'][name] = {'path': resolved, 'sha256': hashlib.sha256(binary).hexdigest(),
                                      'version': version.decode().rstrip('\n'),
                                      'architecture': architecture(binary)}
    help_text = command(['docker', 'exec', container, 'mariadb-dump', '--no-defaults', '--help'])
    (output/'dump-help.txt').write_bytes(help_text)
    query = ("SELECT VERSION(), @@version_compile_machine; "
             "SELECT user,host FROM mysql.user WHERE user='root' AND host='localhost'; SELECT 1;")
    startup = command(['docker', 'exec', container, 'mariadb', '--no-defaults', '--user=root',
                       '--batch', '--skip-column-names', '--execute='+query])
    (output/'startup-query.txt').write_bytes(startup)
    observed['startup_query'] = startup.decode()
    (output/'observed.json').write_text(json.dumps(observed, indent=2)+'\n')
    validate(observed, pin, expected_source)
    observed['producer_probe'] = producer_probe(container, command, output)
    require(observed['producer_probe'].get('result') == 'PASS', 'producer probe did not pass')
    # Reject source changes made during acquisition as well as before it.
    require(source_identity(expected_source) == observed['source'], 'source changed during acquisition')
    (output/'observed.json').write_text(json.dumps(observed, indent=2)+'\n')
    return observed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--container', required=True)
    parser.add_argument('--expected-source-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    require(not (args.output/'result.json').exists(), 'refuse stale result receipt')
    result = {'result': 'FAIL', 'scope': 'native identity and bounded TCP producer probe on observed host',
              'application_dump_generated': False, 'dump_imported': False, 'reader_executed': False}
    try:
        pin = json.loads(PIN.read_text())
        observed = capture(args.container, args.expected_source_commit, pin, args.output)
        result.update(result='PASS', source_commit=observed['source']['source_commit'],
                      pin_sha256=hashlib.sha256(PIN.read_bytes()).hexdigest())
    except Exception as error:
        result['error'] = str(error)
    finally:
        (args.output/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
    return 0 if result['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
