import copy
import importlib.util
import json
import re
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('g2_observations',Path(__file__).with_name('observations.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def sample():
    lines=[]
    for group,ids in m.EXPECTED.items():
        for name in sorted(ids):
            lines.append('    G2_OBSERVATION '+json.dumps(dict(test=group+'/fixture',id=name,expected='target',actual='target',pass_=True)).replace('"pass_"','"pass"'))
        lines.append('--- PASS: '+group+' (0.01s)')
    return '\n'.join(lines)+'\nPASS\n'


class EvidenceTests(unittest.TestCase):
    def test_embedded_native_oracles_and_source_inputs(self):
        import hashlib
        root=Path(__file__).resolve().parents[3]
        folder=Path(__file__).parent
        inputs=json.loads((folder/'oracle-inputs.json').read_text())['files_sha256']
        for name,sha in inputs.items():self.assertEqual(sha,hashlib.sha256((root/name).read_bytes()).hexdigest(),name)
        fixture=lambda name:json.loads((root/'tests/fixtures'/name).read_text())
        native=fixture('prepared-p1-native.json')['metadata']
        self.assertEqual(native,{x['name']:x['expected'] for x in m.ORACLE['prepare']})
        vectors=fixture('prepared-p2-values.json');typed=fixture('prepared-p2-native.json')['cases']
        self.assertEqual([{**v,'expected':typed[v['name']]} for v in vectors],m.ORACLE['values'])
        calls=fixture('prepared-p3-native.json')['cases']
        self.assertEqual(set(calls),{x['name'] for x in m.ORACLE['calls']})
        for case in m.ORACLE['calls']:self.assertEqual(calls[case['name']]['trace'],case['trace'])
        matrix=fixture('prepared-p2-matrix-native.json')['cases']
        for case in m.ORACLE['additional']:self.assertEqual(matrix[case['name']]['trace'],case['trace'])
        long=fixture('prepared-long-data-native.json')['cases']
        for case in m.ORACLE['long']:self.assertEqual(long[case['name']]['trace'],case['trace'])
        self.assertEqual((6,19,13,14,6),tuple(len(m.ORACLE[k]) for k in ('prepare','values','additional','calls','long')))

    def test_missing_metadata_reachability_is_incomplete_not_qualified(self):
        lines=sample().splitlines()
        for i,line in enumerate(lines):
            if '"id": "control_prepare"' in line:
                lines[i]=line.replace('"pass": true','"pass": false')
        result=m.analyze('\n'.join(lines)+'\n',0)
        self.assertFalse(result['complete']);self.assertFalse(result['ready'])
        self.assertEqual(1,len(result['metadata_reachability_precondition_failures']))

    def test_complete_scope(self):
        r=m.analyze(sample(),0)
        self.assertTrue(r['ready']);self.assertEqual(241,len(r['observations']))

    def test_each_missing_observation_is_incomplete(self):
        lines=sample().splitlines()
        for index,line in enumerate(lines):
            if 'G2_OBSERVATION ' in line:
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
        log=sample().replace('"pass": true','"pass": false',1).replace('--- PASS: TestG2PrepareMetadata','--- FAIL: TestG2PrepareMetadata')
        log=log[:-5]+'FAIL\n'
        r=m.analyze(log,1)
        self.assertTrue(r['complete']);self.assertFalse(r['ready']);self.assertEqual(1,len(r['mismatches']))

    def test_exit_timeout_skip_and_truncation_never_pass(self):
        self.assertFalse(m.analyze(sample(),1)['ready'])
        self.assertFalse(m.analyze(sample(),124)['complete'])
        self.assertFalse(m.analyze(sample().replace('--- PASS:','--- SKIP:',1),0)['complete'])
        self.assertFalse(m.analyze(sample()[:-6],0)['complete'])

    def test_duplicate_or_missing_group_never_complete(self):
        self.assertFalse(m.analyze('--- PASS: TestG2PrepareMetadata (0s)\n'+sample(),0)['complete'])
        self.assertFalse(m.analyze(sample().replace('--- PASS: TestG2PrepareMetadata (0.01s)\n',''),0)['complete'])

    def test_only_one_exact_fixture_extension(self):
        base={'a.go':'a','b.s':'b','code/data.bin':'d','receipt.json':'r'}
        actual=dict(base);actual['cmd/issue65-wire/g2_test.go']='fixture'
        self.assertEqual(4,m.require_extension(actual,base,'fixture'))
        for name in ('a.go','b.s','code/data.bin','cmd/issue65-wire/g2_test.go'):
            for mutation in ('change','delete'):
                bad=dict(actual)
                if mutation=='change':bad[name]='wrong'
                else:del bad[name]
                with self.assertRaises(ValueError):m.require_extension(bad,base,'fixture')
        bad=dict(actual);bad['extra.go']='new'
        with self.assertRaises(ValueError):m.require_extension(bad,base,'fixture')
        with self.assertRaises(ValueError):m.require_extension(actual,actual,'fixture')

    def test_fixture_deadlines_fit_fixed_guest_open_contract(self):
        root=Path(__file__).resolve().parents[3]
        patch=(root/'guest/experimental.patch').read_text()
        match=re.search(r'need\(ms>=(\d+)&&ms<=(\d+),"deadline configuration"\)',patch)
        self.assertIsNotNone(match, 'review changed guest OPEN envelope')
        low,high=map(int,match.groups())
        fixture=Path(__file__).with_name('g2_test.go.txt').read_text()
        values=re.findall(r'rootFor\(t, ([^)]+)\)',fixture)
        self.assertTrue(values)
        settings=re.findall(r'\bms\s*(?::=|=)\s*(?:uint64\((\d+)\)|(\d+))',fixture)
        self.assertEqual(len(settings),len(re.findall(r'\bms\s*(?::=|=)',fixture)))
        numbers=[int(a or b) for a,b in settings]
        self.assertEqual([1000,2000],numbers)
        for value in values:
            for number in numbers if value=='ms' else [int(value)]:
                self.assertLessEqual(low,number)
                self.assertLessEqual(number,high)

    def test_probe_imports_its_own_observer(self):
        # The earlier probe imports a same-named module; the new observer must
        # retain its own file identity instead of silently using that parser.
        spec=importlib.util.spec_from_file_location('g2_probe',Path(__file__).with_name('probe.py'))
        probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
        self.assertEqual(probe.observer.EXPECTED,m.EXPECTED)
        self.assertTrue(probe.observer.analyze(sample(),0)['ready'])

if __name__=='__main__':unittest.main()
