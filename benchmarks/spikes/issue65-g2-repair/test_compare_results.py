import copy,importlib.util,json,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('g2_compare',HERE/'compare_results.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.reference=json.loads((HERE.parent/'issue65-g2/evidence/macos/g2-result.json').read_text());self.actual=copy.deepcopy(self.reference)
    def test_all241_match(self):
        result=module.compare(self.reference,self.actual);self.assertTrue(result['matched']);self.assertEqual(241,result['compared_observations'])
    def fatal(self):return next(r for r in self.actual['observations'] if r['id']=='mid_output_active')
    def test_only_drain_quantity_may_vary(self):
        self.fatal()['actual']['drained_native_bytes']+=13
        self.assertTrue(module.compare(self.reference,self.actual)['matched'])
        self.fatal()['actual']['prefix_valid']=False
        self.assertFalse(module.compare(self.reference,self.actual)['matched'])
    def test_drain_quantity_schema(self):
        for value in (-1,True,'1'):
            self.fatal()['actual']['drained_native_bytes']=value
            with self.assertRaises(ValueError):module.compare(self.reference,self.actual)
    def test_changed_expectation_or_outcome_is_visible(self):
        self.actual['observations'][0]['pass']=not self.actual['observations'][0]['pass']
        self.assertFalse(module.compare(self.reference,self.actual)['matched'])
    def test_actual_difference_is_visible(self):
        self.actual['observations'][0]['actual']='changed'
        self.assertFalse(module.compare(self.reference,self.actual)['matched'])
    def test_missing_and_duplicate_are_not_matched(self):
        removed=self.actual['observations'].pop()
        self.assertFalse(module.compare(self.reference,self.actual)['matched'])
        self.actual['observations'].append(self.actual['observations'][0])
        with self.assertRaises(ValueError):module.compare(self.reference,self.actual)
    def test_guest_cannot_change(self):
        self.actual['guest_sha256']='0'*64
        with self.assertRaises(ValueError):module.compare(self.reference,self.actual)
if __name__=='__main__':unittest.main()
