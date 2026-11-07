import copy,difflib,hashlib,importlib.util,json,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('handshake_contract_test',HERE/'handshake_contract.py');contract=importlib.util.module_from_spec(spec);spec.loader.exec_module(contract)
class ContractTests(unittest.TestCase):
    def setUp(self):
        self.raw=(HERE.parent/'issue65-g2/g2_test.go.txt').read_bytes()
        self.original=json.loads((HERE/'evidence/macos-g2-result.json').read_text())
    def test_only_named_two_expectation_lines_change(self):
        prepared=contract.fixture(self.raw)
        self.assertEqual(self.raw,prepared.replace(contract.NEW,contract.OLD))
        changes=[line for line in difflib.ndiff(self.raw.decode().splitlines(),prepared.decode().splitlines()) if line.startswith(('- ','+ '))]
        self.assertEqual(4,len(changes));self.assertEqual(1,prepared.count(contract.NEW))
    def test_fixture_preimage_fails_closed(self):
        with self.assertRaises(ValueError):contract.fixture(self.raw+b'\n')
        with self.assertRaises(ValueError):contract.fixture(contract.fixture(self.raw))
    def test_saved_native_packet_matches_approved_contract_without_rewriting_history(self):
        before=copy.deepcopy(self.original);changed=contract.reference_for_comparison(self.original)
        self.assertEqual(before,self.original)
        self.assertFalse(changed['ready']);self.assertEqual(self.original['mismatches'],changed['mismatches'])
        differences=[(a,b) for a,b in zip(self.original['observations'],changed['observations']) if a!=b]
        self.assertEqual(1,len(differences));a,b=differences[0]
        self.assertEqual(a['actual'],b['actual']);self.assertTrue(b['pass']);self.assertEqual('native1043/08S01',b['expected'])
        review=contract.adjudicate(self.original);self.assertEqual(241,review['satisfy_current_contract']);self.assertEqual([],review['remaining_current_contract_mismatches']);self.assertFalse(review['new_runtime_executed'])
    def test_wrong_packet_or_read_error_is_not_accepted(self):
        for actual in ({'packet':'ff1504233238303030','error':'<nil>'},{'packet':'ff1304234859303030','error':'<nil>'},{'packet':'ff1304233038533031','error':'EOF'},{'packet':'00','error':'<nil>'}):
            changed=copy.deepcopy(self.original)
            next(r for r in changed['observations'] if (r['test'],r['id'])==contract.KEY)['actual']=actual
            with self.assertRaises(ValueError):contract.reference_for_comparison(changed)
    def test_missing_duplicate_and_unexpected_expectation_reject(self):
        rows=self.original['observations'];row=next(r for r in rows if (r['test'],r['id'])==contract.KEY)
        for values in ([r for r in rows if r is not row],rows+[row]):
            changed=copy.deepcopy(self.original);changed['observations']=values
            with self.assertRaises(ValueError):contract.reference_for_comparison(changed)
        row['expected']='another expectation'
        with self.assertRaises(ValueError):contract.reference_for_comparison(self.original)
    def test_other_failure_remains_a_failure(self):
        self.original['observations'][0]['pass']=False
        review=contract.adjudicate(self.original);self.assertEqual(240,review['satisfy_current_contract']);self.assertEqual(1,len(review['remaining_current_contract_mismatches']))
    def test_linux_evidence_matches_approved_contract(self):
        result=json.loads((HERE/'evidence/linux-g2-legacy-result.json').read_text())
        self.assertFalse(result['ready']);self.assertEqual(1,len(result['mismatches']))
        review=contract.adjudicate(result);self.assertEqual(241,review['satisfy_current_contract']);self.assertEqual([],review['remaining_current_contract_mismatches'])
    def test_partial_evidence_is_not_qualified(self):
        self.original['complete']=False
        with self.assertRaises(ValueError):contract.adjudicate(self.original)
if __name__=='__main__':unittest.main()
