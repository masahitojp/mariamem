"""Bounded format/failure mutations, independent of runtime execution."""
import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent/'dump_import_acceptance'))
from routes import input_bytes
from run import assess


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
            sqlstate='42S02' if mode == 'sql_failure' else None,
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


@pytest.mark.parametrize('route', ['reader', 'native'])
@pytest.mark.parametrize('wrong_state', ['HY000', '42000', None])
def test_sql_failure_requires_exact_sqlstate(route, wrong_state):
    code, counts, events = scenario(route, 'sql_failure')
    assert assess(route, 'sql_failure', code, counts, events, 0)
    next(e for e in events if e['event'] == 'prepare_error')['sqlstate'] = wrong_state
    assert not assess(route, 'sql_failure', code, counts, events, 0)
