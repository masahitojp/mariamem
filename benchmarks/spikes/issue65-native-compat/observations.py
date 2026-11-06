"""Fail-closed accounting for the fixed-guest compatibility campaign."""
import json
import re

EXPECTED = {
    'TestCompatCredentials', 'TestCompatCapabilities', 'TestCompatPreparedState',
    'TestCompatCapacity', 'TestCompatLiveCapacity', 'TestCompatFatalEOF',
    'TestCompatFullWindow',
}


def analyze(log, exit_code):
    cases = re.findall(r'^--- (PASS|FAIL|SKIP): (TestCompat\w+) \(([^)]+)\)$', log, re.M)
    names = [name for _, name, _ in cases]
    observations = []
    for line in log.splitlines():
        if 'COMPAT_OBSERVATION ' not in line:
            continue
        row = json.loads(line.split('COMPAT_OBSERVATION ', 1)[1])
        if (set(row) != {'test', 'id', 'expected', 'actual', 'pass'}
                or type(row['pass']) is not bool
                or row['test'].split('/')[0] not in EXPECTED):
            raise ValueError('invalid observation identity/schema')
        observations.append(row)
    complete = (set(names) == EXPECTED and len(names) == len(EXPECTED)
                and all(status != 'SKIP' for status, _, _ in cases)
                and (log.endswith('PASS\n') or log.endswith('FAIL\n'))
                and exit_code in (0, 1))
    covered = {row['test'].split('/')[0] for row in observations}
    ready = (complete and exit_code == 0 and log.endswith('PASS\n')
             and all(status == 'PASS' for status, _, _ in cases)
             and covered == EXPECTED and all(row['pass'] for row in observations))
    return {'result': 'PASS for scoped compatibility observations' if ready else
            ('NOT_READY: contract mismatches' if complete else 'INCOMPLETE: missing execution evidence'),
            'complete': complete, 'ready': ready,
            'cases': [{'name': n, 'result': s, 'elapsed': t} for s, n, t in cases],
            'missing_cases': sorted(EXPECTED-set(names)),
            'observations': observations,
            'mismatches': [row for row in observations if not row['pass']],
            'exit_code': exit_code}
