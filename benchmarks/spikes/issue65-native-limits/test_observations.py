import copy
import importlib.util
import json
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('limits_observations',Path(__file__).with_name('observations.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def sample():
    lines=[]
    for group,ids in m.EXPECTED.items():
        for name in sorted(ids):
            lines.append('    LIMITS_OBSERVATION '+json.dumps(dict(test=group+'/fixture',id=name,expected='target',actual='target',pass_=True)).replace('"pass_"','"pass"'))
        lines.append('--- PASS: '+group+' (0.01s)')
    return '\n'.join(lines)+'\nPASS\n'


class EvidenceTests(unittest.TestCase):
    def test_complete_scope(self):
        r=m.analyze(sample(),0)
        self.assertTrue(r['ready']);self.assertEqual(38,len(r['observations']))

    def test_each_missing_observation_is_incomplete(self):
        lines=sample().splitlines()
        for index,line in enumerate(lines):
            if 'LIMITS_OBSERVATION ' in line:
                r=m.analyze('\n'.join(lines[:index]+lines[index+1:])+'\n',0)
                self.assertFalse(r['complete']);self.assertEqual(1,len(r['missing_observations']))

    def test_duplicate_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'duplicate'):
            m.analyze(sample().splitlines()[0]+'\n'+sample(),0)

    def test_unknown_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'unknown'):
            m.analyze(sample().replace('"id": "','"id": "unexpected_',1),0)

    def test_nonboolean_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'schema'):
            m.analyze(sample().replace('"pass": true','"pass": 1',1),0)

    def test_failure_retained_without_relabel(self):
        log=sample().replace('"pass": true','"pass": false',1).replace('--- PASS: TestLimitsCommands','--- FAIL: TestLimitsCommands')
        log=log[:-5]+'FAIL\n'
        r=m.analyze(log,1)
        self.assertTrue(r['complete']);self.assertFalse(r['ready']);self.assertEqual(1,len(r['mismatches']))

    def test_exit_timeout_skip_and_truncation_never_pass(self):
        self.assertFalse(m.analyze(sample(),1)['ready'])
        self.assertFalse(m.analyze(sample(),124)['complete'])
        self.assertFalse(m.analyze(sample().replace('--- PASS:','--- SKIP:',1),0)['complete'])
        self.assertFalse(m.analyze(sample()[:-6],0)['complete'])

    def test_duplicate_or_missing_group_never_complete(self):
        self.assertFalse(m.analyze('--- PASS: TestLimitsCommands (0s)\n'+sample(),0)['complete'])
        self.assertFalse(m.analyze(sample().replace('--- PASS: TestLimitsCommands (0.01s)\n',''),0)['complete'])

    def test_only_one_exact_fixture_extension(self):
        base={'a.go':'a','b.s':'b','code/data.bin':'d','receipt.json':'r'}
        actual=dict(base);actual['cmd/issue65-wire/limits_test.go']='fixture'
        self.assertEqual(4,m.require_extension(actual,base,'fixture'))
        for name in ('a.go','b.s','code/data.bin','cmd/issue65-wire/limits_test.go'):
            for mutation in ('change','delete'):
                bad=dict(actual)
                if mutation=='change':bad[name]='wrong'
                else:del bad[name]
                with self.assertRaises(ValueError):m.require_extension(bad,base,'fixture')
        bad=dict(actual);bad['extra.go']='new'
        with self.assertRaises(ValueError):m.require_extension(bad,base,'fixture')
        with self.assertRaises(ValueError):m.require_extension(actual,actual,'fixture')

    def test_probe_imports_its_own_observer(self):
        # The earlier probe imports a same-named module; the new observer must
        # retain its own file identity instead of silently using that parser.
        spec=importlib.util.spec_from_file_location('limits_probe',Path(__file__).with_name('probe.py'))
        probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
        self.assertEqual(probe.limits.EXPECTED,m.EXPECTED)
        self.assertTrue(probe.analyze(sample(),0)['ready'])

if __name__=='__main__':unittest.main()
