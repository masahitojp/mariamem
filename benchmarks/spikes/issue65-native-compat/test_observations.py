import json
import unittest
from observations import analyze, EXPECTED


def fixture():
    lines = []
    for name in sorted(EXPECTED):
        lines.append('COMPAT_OBSERVATION '+json.dumps({'test':name,'id':'probe','expected':1,'actual':1,'pass':True}))
        lines.append('--- PASS: '+name+' (0.01s)')
    return '\n'.join(lines)+'\nPASS\n'


class EvidenceAccounting(unittest.TestCase):
    def test_exact_pass(self):
        self.assertTrue(analyze(fixture(), 0)['ready'])

    def test_missing_or_duplicate_case_cannot_pass(self):
        log = fixture()
        for changed in [log.replace('--- PASS: TestCompatFatalEOF (0.01s)\n',''),
                        log.replace('PASS\n','--- PASS: TestCompatFatalEOF (0.01s)\nPASS\n')]:
            self.assertFalse(analyze(changed, 0)['complete'])

    def test_false_observation_cannot_hide_behind_go_pass(self):
        result = analyze(fixture().replace('"pass": true','"pass": false',1),0)
        self.assertFalse(result['ready']); self.assertEqual(len(result['mismatches']),1)

    def test_failed_case_keeps_observations(self):
        log=fixture().replace('--- PASS: TestCompatCapacity','--- FAIL: TestCompatCapacity')
        result=analyze(log.removesuffix('PASS\n')+'FAIL\n',1)
        self.assertTrue(result['complete']);self.assertFalse(result['ready'])
        self.assertEqual(len(result['observations']),len(EXPECTED))

    def test_skip_crash_and_inconsistent_exit_are_not_ready(self):
        for log,code in [(fixture().replace('--- PASS: TestCompatCapacity','--- SKIP: TestCompatCapacity'),0),
                         (fixture().removesuffix('PASS\n')+'panic: timeout\n',2),
                         (fixture(),1)]:
            self.assertFalse(analyze(log,code)['ready'])

    def test_schema_and_unknown_identity_rejected(self):
        for log in [fixture().replace('"pass": true','"pass": "true"',1),
                    fixture().replace('"test": "TestCompatCapacity"','"test": "TestOther"',1),
                    fixture()+'COMPAT_OBSERVATION {bad json}\n']:
            with self.assertRaises((ValueError,json.JSONDecodeError)):analyze(log,0)

    def test_all_case_names_without_observations_cannot_pass(self):
        log='\n'.join(line for line in fixture().splitlines() if not line.startswith('COMPAT_OBSERVATION'))+'\n'
        self.assertFalse(analyze(log,0)['ready'])

if __name__ == '__main__':unittest.main()
