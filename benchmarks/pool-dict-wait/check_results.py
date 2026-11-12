#!/usr/bin/env python3
"""Read-only controlled-evidence replay; not a natural PREPARE causal oracle."""
import argparse
import copy
import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent

def check(rows):
    expected = {(a, c, r) for r in (1, 2, 3) for c in (1, 16)
                for a in ('pending_unreported', 'pending_reported', 'late_submit', 'uncontended', 'nonpool')
                if a != 'nonpool' or c == 1}
    assert len(rows) == len(expected) == 27
    assert {(r['Arm'], r['Concurrency'], r['Repeat']) for r in rows} == expected
    for r in rows:
        arm = r['Arm']
        assert r['Result'] == 'PASS'
        assert r['MappingsBefore'] == r['MappingsAfter'] == 0
        assert r['Evicted'] == r['RefBalance'] == r['WaitingAfter'] == 0
        assert r['FlagsBefore'] & 6 == r['FlagsAfter'] & 6 == 0
        workers = 1 if arm in ('nonpool', 'uncontended') else 2
        assert r['Created'] == r['Retired'] == workers
        events = r['Events']
        names = [e['Name'] for e in events]
        assert len({e['Pool'] for e in events}) == 1 and events[0]['Pool'] > 0
        assert names.count('worker_init') == names.count('pending_clear') == names.count('worker_retire') == workers
        assert names.count('timer_suppressed') == names.count('pool_disposed') == 1
        assert names[-1] == 'pool_disposed'
        assert names.count('pending_refusal') == (0 if arm in ('late_submit', 'nonpool') else 1)
        notify = 1 if arm in ('pending_reported', 'nonpool') else 0
        assert r['NotifyBegin'] == r['NotifyEnd'] == names.count('notify_begin') == names.count('notify_end') == notify
        if arm == 'uncontended':
            assert r['SlowEntries'] == r['FutexCalls'] == r['WaitingDuring'] == 0
            assert 'dict_slow_begin' not in names and 'dict_futex' not in names
            assert names.index('a_end') < names.index('b_run')
        else:
            assert r['SlowEntries'] == names.count('dict_slow_begin') == 1
            assert r['FutexCalls'] == names.count('dict_futex') >= 1
            assert r['Exclusion'] is True
            assert names.index('dict_slow_begin') < names.index('dict_futex') < names.index('owner_release') < names.index('dict_acquired')
            assert r['WaitingDuring'] == (1 if arm == 'pending_reported' else 0)
            if notify:
                assert names.index('dict_slow_begin') < names.index('notify_begin') < names.index('dict_acquired') < names.index('notify_end')
        if arm != 'nonpool':
            assert names.index('pending_clear') < names.index('a_start')
            if arm == 'late_submit':
                assert names.index('dict_futex') < names.index('submit_b') < names.index('b_run')
            else:
                assert names.index('submit_b') < names.index('pending_refusal') < names.index('pending_clear')
        if arm == 'pending_unreported':
            assert [r[k] for k in ('Occupied', 'Waiting', 'Long', 'Pending', 'Queued')] == [1, 0, 0, 0, 1]
            assert 50 <= r['ObservationMS'] < 250
            assert names.count('maintenance') == 1
            assert names.index('dict_futex') < names.index('maintenance') < names.index('b_run') < names.index('owner_release')
        else:
            assert 'maintenance' not in names
            if arm == 'pending_reported':
                assert names.index('notify_begin') < names.index('b_run') < names.index('owner_release')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cases', type=pathlib.Path, default=HERE / 'results/cases.json')
    parser.add_argument('--checksums', action='store_true')
    args = parser.parse_args()
    rows = json.loads(args.cases.read_text())
    check(rows)
    mutations = [lambda x: x.pop(), lambda x: x[0].update(Result='PASS', Waiting=1),
                 lambda x: x[0].update(FutexCalls=0), lambda x: x[0].update(Exclusion=False),
                 lambda x: x[0].update(RefBalance=1), lambda x: x[1].update(NotifyEnd=0),
                 lambda x: x[1].update(WaitingAfter=1), lambda x: x[0].update(MappingsAfter=1)]
    for mutate in mutations:
        bad = copy.deepcopy(rows)
        mutate(bad)
        try:
            check(bad)
        except AssertionError:
            continue
        raise AssertionError('corrupt evidence accepted')
    if args.checksums:
        for name, digest in json.loads((HERE / 'SHA256SUMS.json').read_text()).items():
            assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == digest, name
    print('PASS: 27 fixed dictionary cases; progress/exclusion/accounting/disposal; 8 corrupt-evidence controls')
    print('Natural PREPARE causality and performance remain unmeasured.')

if __name__ == '__main__':
    main()
