"""Keep the claimed finite repair and exact source/guest references reviewable."""
import hashlib,importlib.util,json,re,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
probe=load('g2_repair_reference_probe',HERE/'probe.py')
def record(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
class References(unittest.TestCase):
    def test_original_runtime_oracles_unchanged(self):
        self.assertEqual('804f48fa64a4467a879c3fcd65eb14b6a2b8dda53cf4bade570e163eabc0fd77',sha(HERE.parent/'issue65-prepared-input/g1_test.go.txt'))
        self.assertEqual('a13951d5117558b1ccfa5df7b32edb0ddc68f9d0e2a7b41a6899fa8b0751efb4',sha(HERE.parent/'issue65-g2/g2_test.go.txt'))
    def test_ten_repairs_no_pass_regressions_one_visible_mismatch(self):
        before=record(HERE.parent/'issue65-g2/evidence/macos/g2-result.json');after=record(HERE/'evidence/macos-g2-result.json')
        self.assertTrue(after['complete']);self.assertFalse(after['ready']);self.assertEqual(241,len(after['observations']));self.assertEqual([],after['missing_observations'])
        previous={(r['test'],r['id']):r for r in before['observations']};fixed=[]
        for r in after['observations']:
            old=previous[(r['test'],r['id'])];self.assertEqual(old['expected'],r['expected'])
            if old['pass']:self.assertTrue(r['pass'],r['id'])
            elif r['pass']:fixed.append(r['id'])
        self.assertEqual(10,len(fixed));self.assertEqual(1,len(after['mismatches']))
        self.assertEqual(before['mismatches'][-1],after['mismatches'][0])
        self.assertEqual('short_fixed_header',after['mismatches'][0]['id'])
        self.assertEqual(probe.G2_REFERENCE_SHA256,sha(HERE/'evidence/macos-g2-result.json'))
    def test_new_guest_and_source_reference(self):
        p=probe.fix;ref=record(HERE/'evidence/macos-reference.json');guest=record(HERE/'evidence/guest.json')
        self.assertEqual(p.SOURCE_REFERENCE_SHA256,sha(HERE/'evidence/macos-reference.json'))
        self.assertEqual(283,len(ref['source_inventory']))
        self.assertEqual(p.CAPTURE_FIXTURE_AFTER,ref['source_inventory'][p.CAPTURE_FIXTURE_NAME])
        self.assertEqual(p.GUEST_SHA,ref['guest_sha256']);self.assertEqual(p.GUEST_SOURCE,ref['guest_source_commit']);self.assertEqual(p.HOST_SOURCE,ref['host_source_commit'])
        self.assertEqual('UNQUALIFIED',guest['result']);self.assertEqual(p.GUEST_SHA,guest['guest_sha256']);self.assertEqual(p.GUEST_SOURCE,guest['source_commit'])
    def test_worker_bodies_and_abi(self):
        binding=record(HERE/'binding/identity.json');self.assertEqual(probe.fix.GUEST_SHA,binding['guest_sha256'])
        self.assertEqual({'start_args.pthread':16,'pthread.map_base':40,'pthread.map_size':44},binding['ABI_offsets'])
        self.assertEqual({'free','yield','entry'},{r['role'] for r in binding['functions'].values()})
        for item in binding['functions'].values():
            body=(HERE/'binding'/(item['function']+'.txt')).read_text()
            self.assertEqual(item['normalized_sha256'],hashlib.sha256(re.sub(r'\s+','',body).encode()).hexdigest())
            self.assertTrue(binding['review'][item['role']]['complete_body_equal_after_recorded_relocation'])
    def test_exact_single_fixture_extension(self):
        build=record(HERE/'evidence/macos-build-summary.json')
        self.assertEqual(284,build['staged_go_assembly_data_files']);self.assertEqual(7420,build['baseline_source_inventory_file_count']);self.assertEqual(7421,build['source_inventory_file_count'])
        self.assertEqual('cmd/issue65-wire/g2_test.go',build['only_extension'])
        self.assertEqual(sha(HERE.parent/'issue65-g2/g2_test.go.txt'),build['fixture_sha256'])
    def test_ci_pins_and_preparation_checkpoint(self):
        workflow=(ROOT/'.github/workflows/issue65-g2-repair.yml').read_text()
        self.assertEqual(2,workflow.count('ref: '+probe.fix.GUEST_SOURCE))
        self.assertIn('branches: [experiment/issue65-g2-repair]',workflow)
        self.assertIn('build_checked_guest.py',(HERE/'probe_baseline.py').read_text())
        self.assertIn("kwargs.get('phase')=='guest:prepare:0'",(HERE/'build_checked_guest.py').read_text())
        self.assertIn('if: always()',workflow)
if __name__=='__main__':unittest.main()
