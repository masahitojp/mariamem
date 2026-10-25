"""Independent native-client route and bounded reader route, test harness only."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

from oracles import INIT, SESSION, connect, session
from reader import ImportFailure, execute

HERE = Path(__file__).resolve().parent
CANONICAL_SHA256 = '081ef0273c3625cb1d2a143415b90e9845bc2132312853a047eed09c8807e87c'


def input_bytes(mode):
    raw = (HERE/'input/application.sql').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == CANONICAL_SHA256
    assert json.loads((HERE/'input/input-manifest.json').read_text())['dump_sha256'] == CANONICAL_SHA256
    if mode == 'sql_failure':
        raw += (b'\nCREATE TABLE spike_partial(id INT PRIMARY KEY) ENGINE=InnoDB;\n'
                b'INSERT INTO missing_dump_oracle(id) VALUES(1);\n')
    elif mode == 'malformed':
        raw += b"\nSELECT 'unterminated_dump_oracle\n"
    elif mode == 'source':
        raw += b'\nSOURCE forbidden_dump_oracle.sql\n'
    else:
        assert mode == 'success'
    return raw


def empty_schema(info, *, drop=False):
    with connect(info, schema=info.get('database', 'test')) as connection:
        with connection.cursor() as cursor:
            if drop:
                cursor.execute('DROP DATABASE IF EXISTS app')
            cursor.execute('CREATE DATABASE app CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')


def native_import(info, raw, command, output):
    argv = [*command, '--no-defaults', '--protocol=tcp', '--host='+info['host'],
            '--port='+str(info['port']), '--user='+info['user'],
            '--default-character-set=utf8mb4', '--batch', '--raw', '--skip-column-names',
            '--init-command='+INIT, 'app']
    # The canonical file is an unchanged prefix. A separate harness query reads
    # restored session state on this same client connection after the import.
    # It is never written into or described as part of the canonical dump.
    trailer = ("\nSELECT '__dump_session__',"+','.join(SESSION)+";\n").encode()
    process = subprocess.run(argv, input=raw+trailer, capture_output=True, timeout=90)
    output.mkdir(parents=True, exist_ok=True)
    (output/'native.stdout.txt').write_bytes(process.stdout)
    (output/'native.stderr.txt').write_bytes(process.stderr)
    (output/'session-probe.sql').write_bytes(trailer)
    (output/'native-command.json').write_text(json.dumps(argv, indent=2)+'\n')
    if process.returncode:
        message = process.stderr.decode('utf8', errors='replace')
        error = re.search(r'ERROR\s+(\d+)\s+\(([A-Z0-9]+)\)', message)
        line = re.search(r'(?:at|in) line (\d+)', message)
        number = int(line[1]) if line else None
        offsets = [0]
        offsets.extend(i+1 for i, char in enumerate(raw) if char == 10)
        location = dict(ordinal=None, line_start=number, line_end=number,
            byte_start=offsets[number-1] if number and number <= len(offsets) else None,
            byte_end=offsets[number] if number and number < len(offsets) else len(raw))
        reason = 'sandbox_rejected_client_command' if 'sandbox' in message.lower() else 'native_client_error'
        failure = ImportFailure(reason, stage='native_client', location=location,
                                errno=int(error[1]) if error else None,
                                sqlstate=error[2] if error else None)
        failure.details['exit_code'] = process.returncode
        raise failure
    markers = [line for line in process.stdout.decode().splitlines() if line.startswith('__dump_session__\t')]
    assert len(markers) == 1, 'session probe did not execute exactly once'
    state = markers[0].split('\t')[1:]
    state[1] = sorted(state[1].split(','))
    state[5:9] = list(map(int, state[5:9]))
    return {'session_after': state, 'exit_code': process.returncode,
            'dump_sha256': hashlib.sha256(raw).hexdigest(),
            'native_ordinal_available': False}


def load(info, route, mode, command, output):
    raw = input_bytes(mode)
    output.mkdir(parents=True, exist_ok=True)
    (output/'executed-input.sql').write_bytes(raw)
    # Establish/check the same explicit initial settings on reader connections.
    # Native client sets exactly INIT through --init-command.
    with connect(info) as connection:
        before = session(connection)
        if route == 'reader':
            result = execute(connection, raw)
            result['session_after'] = session(connection)
        else:
            assert route == 'native'
            result = native_import(info, raw, command, output)
    result['session_before'] = before
    assert result['session_after'] == before, 'dump failed to restore initial session state'
    return result
