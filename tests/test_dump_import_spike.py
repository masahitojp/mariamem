"""Bounded format/failure mutations, independent of runtime execution."""
import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent/'dump_import_spike'))
from reader import ImportFailure, execute, frame
from routes import input_bytes
from run import assess


def test_original_dump_preserves_routines_comments_and_string_semicolons():
    statements, directives = frame(input_bytes('success'))
    assert len(statements) == 90
    assert [d['value'] for d in directives] == [';;', ';', ';;', ';']
    routines = [s for s in statements if b'CREATE DEFINER=' in s.sql]
    assert len(routines) == 2
    assert all(s.sql.count(b';') >= 2 for s in routines)
    assert b'/*M!999999\\- enable the sandbox mode */' in statements[0].sql
    assert any(b'/*M!100616 SET NOTE_VERBOSITY=' in s.sql for s in statements)
    data = [s for s in statements if b'INSERT INTO `user_import_values`' in s.sql]
    assert len(data) == 1 and b'0x00273B5CFF' in data[0].sql
    assert b'path; newline' in data[0].sql


@pytest.mark.parametrize('raw,reason', [
    (b"SELECT 'missing", 'unterminated_quote'),
    (b'SELECT 1 /* missing', 'unterminated_block_comment'),
    (b'SELECT 1', 'missing_final_delimiter'),
    (b'DELIMITER\n', 'unsupported_or_malformed_delimiter'),
    (b'DELIMITER //\n', 'unsupported_or_malformed_delimiter'),
    (b'SOURCE forbidden.sql\n', 'unsupported_client_command'),
    (b'\\. forbidden.sql\n', 'unsupported_client_command'),
])
def test_reject_before_any_execution(raw, reason):
    class Unopened:
        def cursor(self):
            raise AssertionError('execution began before preflight')
    with pytest.raises(ImportFailure) as failure:
        execute(Unopened(), raw)
    assert failure.value.details['reason'] == reason
    assert failure.value.details['stage'] == 'preflight'


def test_comment_and_quote_directives_are_not_client_commands():
    statements, _ = frame(b"SELECT 'SOURCE x; it''s fine';\n/* SOURCE x */\nSELECT 2;\n")
    assert len(statements) == 2
    raw = 'SELECT \'日本語;\';\nSOURCE absent.sql\n'.encode()
    with pytest.raises(ImportFailure) as failure:
        frame(raw)
    assert failure.value.details['location']['byte_start'] == raw.index(b'SOURCE')
    assert failure.value.details['location']['line_start'] == 2


def scenario(route, mode):
    events = [dict(event='source_start', id='source'), dict(event='prepare_start'),
              dict(event='preparation_connections_closed'),
              dict(event='source_cleanup', closed=True, host_reaped=True, directory_removed=True)]
    if mode == 'success':
        events += [dict(event='prepared_state', reference_equal=True),
                   dict(event='snapshot_attempt'), dict(event='snapshot_success'),
                   dict(event='preparation_disconnected', active_connections=0),
                   dict(event='test_pass', name='commit', child='first'),
                   dict(event='test_pass', name='independent_initial_state', child='second')]
        return 0, dict(tests=2, errors=0, failures=0, skipped=0), events
    raw = input_bytes(mode)
    token = {'sql_failure': b'INSERT INTO missing_dump_oracle',
             'malformed': b"'unterminated_dump_oracle", 'source': b'SOURCE'}[mode]
    start = raw.index(token)
    location = dict(ordinal=92 if mode == 'sql_failure' else 91,
                    byte_start=start, byte_end=len(raw), line_start=raw.count(b'\n', 0, start)+1)
    if route == 'reader':
        error = dict(stage='execute' if mode == 'sql_failure' else 'preflight',
            reason={'sql_failure': 'sql_error', 'malformed': 'unterminated_quote',
                    'source': 'unsupported_client_command'}[mode],
            errno=1146 if mode == 'sql_failure' else None,
            original_exception='ProgrammingError' if mode == 'sql_failure' else None)
    else:
        error = dict(stage='native_client', reason='sandbox_rejected_client_command' if mode == 'source' else 'native_client_error',
                     errno={'sql_failure': 1146, 'malformed': 1064, 'source': None}[mode],
                     sqlstate={'sql_failure': '42S02', 'malformed': '42000', 'source': None}[mode], exit_code=1)
    tables = ['users', 'spike_partial'] if mode == 'sql_failure' else ['users'] if route == 'native' else []
    events += [dict(event='partial_source_state', tables=tables),
               dict(event='prepare_error', route=route, mode=mode, location=location, **error)]
    return 1, dict(tests=2, errors=2, failures=0, skipped=0), events


@pytest.mark.parametrize('route', ['reader', 'native'])
@pytest.mark.parametrize('mode', ['success', 'sql_failure', 'malformed', 'source'])
def test_failure_and_admission_mutations(route, mode):
    code, counts, events = scenario(route, mode)
    assert assess(route, mode, code, counts, events, 0)
    assert not assess(route, mode, code, counts, events, 1)
    for key in ['closed', 'host_reaped', 'directory_removed']:
        mutant = copy.deepcopy(events)
        next(e for e in mutant if e['event'] == 'source_cleanup')[key] = False
        assert not assess(route, mode, code, counts, mutant, 0)
    bad_counts = dict(counts, skipped=1)
    assert not assess(route, mode, code, bad_counts, events, 0)
    if mode != 'success':
        assert not assess(route, mode, code, counts, events+[dict(event='snapshot_attempt')], 0)
        mutant = copy.deepcopy(events)
        next(e for e in mutant if e['event'] == 'prepare_error')['reason'] = 'unrelated_connection_error'
        assert not assess(route, mode, code, counts, mutant, 0)
        if mode == 'sql_failure':
            for key, wrong in [('errno', 1045), ('location', {'byte_start': 0, 'byte_end': 1, 'ordinal': 1, 'line_start': 1})]:
                mutant = copy.deepcopy(events)
                next(e for e in mutant if e['event'] == 'prepare_error')[key] = wrong
                assert not assess(route, mode, code, counts, mutant, 0)
            if route == 'native':
                mutant = copy.deepcopy(events)
                next(e for e in mutant if e['event'] == 'prepare_error')['sqlstate'] = 'HY000'
                assert not assess(route, mode, code, counts, mutant, 0)
