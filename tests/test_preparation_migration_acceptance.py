"""Receipt mutation tests; no native host or migration dependencies required."""
import copy
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    'migration_acceptance', Path(__file__).parent / 'preparation_migration_acceptance/run.py')
acceptance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acceptance)


def fixture_events(mode, workers):
    events = []
    for index in range(workers):
        worker = 'main' if workers == 1 else f'gw{index}'
        current = [
            {'event': 'source_start', 'id': f'source-{worker}'},
            {'event': 'prepare_start'},
            {'event': 'preparation_original_profile_refused'},
            {'event': 'preparation_engines_disposed'},
            {'event': 'source_cleanup', 'closed': True,
             'host_reaped': True, 'directory_removed': True},
        ]
        if mode == 'success':
            current.extend([
                {'event': 'prepared_state'}, {'event': 'snapshot_attempt'},
                {'event': 'snapshot_success'},
                {'event': 'preparation_disconnected', 'active_connections': 0},
            ])
            for cycle in (['first', 'second'] if workers == 1 else [['first', 'second'][index]]):
                for name in ['commit', 'independent_initial_state']:
                    current.append({'event': 'test_pass', 'name': name, 'cycle': cycle,
                                    'child': f'{worker}-{cycle}-{name}'})
        else:
            current.append({'event': 'prepare_error', 'oracle': mode,
                            'stage': 'migration' if mode == 'revision_failure' else 'seed',
                            'exception': 'ProgrammingError', 'original_exception': 'ProgrammingError',
                            'errno': 1146})
        events.extend(dict(event, worker=worker) for event in current)
    return events


def verdict(mode, workers, events=None, **overrides):
    arguments = dict(mode=mode, workers=workers, code=0 if mode == 'success' else 1,
                     counts={'tests': 4, 'errors': 0 if mode == 'success' else 4,
                             'failures': 0, 'skipped': 0},
                     events=fixture_events(mode, workers) if events is None else events, contacts=0)
    arguments.update(overrides)
    return acceptance.assess(**arguments)


@pytest.mark.parametrize('workers', [1, 2])
@pytest.mark.parametrize('mode', ['success', 'revision_failure', 'seed_failure'])
def test_exact_success_and_failures(mode, workers):
    assert verdict(mode, workers)


@pytest.mark.parametrize('workers', [1, 2])
@pytest.mark.parametrize('fault', ['wrong_statement', 'wrong_stage', 'wrong_errno',
    'wrong_exception', 'snapshot', 'test_ran', 'host_alive', 'contacts', 'exit', 'skip'])
def test_failure_rejects_mutations(workers, fault):
    events = fixture_events('revision_failure', workers)
    error = next(e for e in events if e['event'] == 'prepare_error')
    options = {}
    if fault == 'wrong_statement': error['oracle'] = None
    if fault == 'wrong_stage': error['stage'] = 'seed'
    if fault == 'wrong_errno': error['errno'] = 2003
    if fault == 'wrong_exception': error['original_exception'] = 'AssertionError'
    if fault in ('snapshot', 'test_ran'):
        events.append({'event': 'snapshot_attempt' if fault == 'snapshot' else 'test_pass',
                       'worker': events[0]['worker']})
    if fault == 'host_alive':
        next(e for e in events if e['event'] == 'source_cleanup')['host_reaped'] = False
    if fault == 'contacts': options['contacts'] = 1
    if fault == 'exit': options['code'] = 2
    if fault == 'skip': options['counts'] = {'tests': 4, 'errors': 3, 'failures': 0, 'skipped': 1}
    assert not verdict('revision_failure', workers, events, **options)


@pytest.mark.parametrize('fault', ['one_worker', 'shared_source', 'shared_child',
                                  'double_prepare', 'double_snapshot', 'missing_cycle',
                                  'different_error_worker', 'extra_worker', 'repeated_cycle'])
def test_xdist_cannot_hide_worker_or_reuse_defects(fault):
    events = copy.deepcopy(fixture_events('success', 2))
    if fault == 'one_worker': events = [e for e in events if e['worker'] == 'gw0']
    if fault == 'shared_source':
        for e in events:
            if e['event'] == 'source_start': e['id'] = 'shared'
    if fault == 'shared_child':
        for e in events:
            if e['event'] == 'test_pass': e['child'] = 'shared'
    if fault in ('double_prepare', 'double_snapshot'):
        events.append({'event': 'prepare_start' if fault == 'double_prepare' else 'snapshot_attempt', 'worker': 'gw0'})
    if fault == 'missing_cycle':
        next(e for e in events if e['event'] == 'test_pass')['name'] = 'wrong'
    if fault == 'different_error_worker':
        events.append({'event': 'prepare_error', 'worker': 'gw1'})
    if fault == 'extra_worker': events.append({'event': 'prepare_start', 'worker': 'gw2'})
    if fault == 'repeated_cycle':
        for e in events:
            if e['event'] == 'test_pass': e['cycle'] = 'first'
    assert not verdict('success', 2, events)
