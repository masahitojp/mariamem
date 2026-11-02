"""Read-only residual worker attribution from the existing accounting traces.

No CPU/blocked-state inference from an absence of scalar events. No new runtime
measurement and no revision of the preregistered distribution acceptance gate.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path


def encode(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def reduce_one(path):
    raw = path.read_bytes()
    trace = json.loads(raw)
    assert trace['dropped'] == 0
    assert not trace['stacks'] and not trace['routine_stack_capture']
    assert not trace['atomic_wait_notify_hooks']
    events = sorted(trace['events'], key=lambda e: e['ns'])
    instances = collections.defaultdict(list)
    spans = collections.defaultdict(list)
    bindings = {}
    for event in events:
        instances[event['instance']].append(event)
        spans[event['span']].append(event)
        if event['kind'] == 'instance_child':
            bindings[event['a']] = event['instance']
    assert len(bindings) == 49 and len(set(bindings.values())) == 49
    cases = []
    for begin in events:
        if begin['kind'] != 'client_count_begin':
            continue
        end = spans[begin['span']][-1]
        assert end['kind'] == 'client_count_end'
        if end['ns'] - begin['ns'] <= 100_000_000:
            continue
        instance = bindings[begin['a']]
        local = instances[instance]
        policies = []
        for event in local:
            if event['kind'] != 'pool_policy' or not begin['ns'] <= event['ns'] <= end['ns']:
                continue
            group = spans[event['span']]
            assert [e['kind'] for e in group] == ['pool_policy', 'pool_counts', 'pool_waiting']
            active, standby, concurrency = (group[1][k] for k in ['a', 'b', 'c'])
            long_tasks, waiting = group[2]['a'], group[2]['b']
            queued = event['b'] != event['c']
            policies.append(dict(ns=event['ns'], active=active, standby=standby,
                                 concurrency=concurrency, long_tasks=long_tasks,
                                 waiting=waiting, queued=queued,
                                 rejects=active-long_tasks-waiting > concurrency))
        rejecting = next((p for p in policies if p['queued'] and p['rejects']), None)
        if rejecting is None:
            continue
        # Prefer the first rejecting policy inside maintenance for comparability.
        maintenance = [(g[0], g[-1]) for g in spans.values()
                       if g[0]['instance'] == instance and g[0]['kind'] == 'maintenance_begin']
        maintenance_reject = next((p for p in policies if p['queued'] and p['rejects'] and
                                   any(a['ns'] <= p['ns'] <= b['ns'] for a, b in maintenance)), None)
        selection = 'first_rejecting_maintenance' if maintenance_reject else 'first_rejection_no_rejecting_maintenance'
        rejecting = maintenance_reject or rejecting
        at = rejecting['ns']
        running = {}
        tasks = []
        for event in local:
            thread = event['thread']
            if event['kind'] == 'task_start':
                assert thread not in running
                running[thread] = event
            elif event['kind'] == 'task_end':
                start = running.pop(thread)
                assert (start['b'], start['c']) == (event['b'], event['c'])
                tasks.append((start, event))
        assert not running
        workers = []
        for task_begin, task_end in tasks:
            if not task_begin['ns'] <= at < task_end['ns']:
                continue
            thread = task_begin['thread']
            observed = [e for e in local if e['thread'] == thread and
                        task_begin['ns'] <= e['ns'] <= task_end['ns']]
            previous = max((e for e in observed if e['ns'] <= at), key=lambda e: e['ns'])
            following = min((e for e in observed if e['ns'] > at), key=lambda e: e['ns'])
            scopes = [g[0]['kind'] for g in spans.values() if g[0]['instance'] == instance and
                      g[0]['thread'] == thread and g[0]['kind'].endswith('_begin') and
                      g[0]['ns'] <= at < g[-1]['ns']]
            # Calls to the generic wait methods, not a claim about internal flags:
            # methods can no-op for non-worker/long-task states.
            balance = sum(e['kind'] == 'wait_begin_begin' for e in local
                          if e['thread'] == thread and e['ns'] <= at) - sum(
                          e['kind'] == 'wait_end_begin' for e in local
                          if e['thread'] == thread and e['ns'] <= at)
            workers.append(dict(thread=thread, task=task_begin['b'], dispatch_slot=task_begin['c'],
                                task_start_from_count_ms=(task_begin['ns']-begin['ns'])/1e6,
                                task_end_from_count_ms=(task_end['ns']-begin['ns'])/1e6,
                                task_ms=(task_end['ns']-task_begin['ns'])/1e6,
                                open_observed_scopes=sorted(scopes), generic_wait_call_balance=balance,
                                previous_event=previous['kind'], next_event=following['kind'],
                                scalar_event_gap_ms=(following['ns']-previous['ns'])/1e6,
                                state='unclassified_cpu_or_wait' if balance == 0 else 'wait_call_open_not_flag_proof'))
        cases.append(dict(child=begin['a'], instance=instance,
                          count_ms=(end['ns']-begin['ns'])/1e6,
                          policy_from_count_ms=(at-begin['ns'])/1e6, selection=selection,
                          policy={k:v for k,v in rejecting.items() if k != 'ns'},
                          running_tasks_at_policy=len(workers), workers=workers))
    return dict(trace_sha256=hashlib.sha256(raw).hexdigest(), cases=cases)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    records = json.loads((args.raw/'measure-records.json').read_text())
    assert len(records) == 6
    output = {'scope': 'Existing source-bound traces only; no new DB runs or acceptance change', 'runs': {}}
    for record in records:
        output['runs'][record['report']] = dict(variant=record['variant'], **reduce_one(
            args.raw/(record['report']+'.trace.json')))
    data = encode(output)
    if args.check:
        assert args.output.read_bytes() == data
        print('PASS source-bound worker attribution reproduction')
    else:
        args.output.write_bytes(data)
        for name, result in output['runs'].items():
            for case in result['cases']:
                print(name, 'child', case['child'], 'count_ms', round(case['count_ms'], 3),
                      'policy', case['policy'], 'workers',
                      [(w['thread'], round(w['task_ms'], 3), w['generic_wait_call_balance'],
                        w['open_observed_scopes'], round(w['scalar_event_gap_ms'], 3)) for w in case['workers']])


if __name__ == '__main__':
    main()
