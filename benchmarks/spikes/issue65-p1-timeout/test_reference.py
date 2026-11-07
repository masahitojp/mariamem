"""Fail closed on new profile3 source,guest,fixture and workflow pin drift."""
import hashlib,importlib.util,json,re,subprocess,sys,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
probe=load('p1_reference_probe',HERE/'probe.py');baseline=probe.fix
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda n:json.loads((HERE/'evidence'/n).read_text())
class Reference(unittest.TestCase):
 def test_source_is_a_commit(self):
  r=json.loads(subprocess.check_output([sys.executable,ROOT/'scripts/git_identity.py','--root',ROOT,'inspect',baseline.GUEST_SOURCE],text=True))
  self.assertEqual(r['object_type'],'commit');self.assertEqual(r['source_commit'],baseline.GUEST_SOURCE);self.assertEqual(baseline.HOST_SOURCE,baseline.GUEST_SOURCE)
 def test_guest_source_and_template_pins(self):
  r=read('macos-reference.json');self.assertRegex(baseline.GUEST_SHA,r'^[0-9a-f]{64}$');self.assertEqual(r['guest_sha256'],baseline.GUEST_SHA);self.assertEqual(r['host_source_commit'],baseline.HOST_SOURCE);self.assertEqual(r['guest_source_commit'],baseline.GUEST_SOURCE)
  self.assertEqual(sha(HERE/'evidence/macos-reference.json'),baseline.SOURCE_REFERENCE_SHA256)
  for name in ('main.go.txt','runtime_wire.go.txt','completion_probe.go.txt','owner_native_test.go.txt','timeout_native_test.go.txt','timeout_contract_test.go.txt'):
   self.assertEqual(r['prototype_templates_sha256'][name],sha(HERE/name),name)
  for name in ('owner.go','owner_test.go'):
   self.assertEqual(r['prototype_templates_sha256'][name+'.txt'],sha(ROOT/'internal/nativewire'/name))
 def test_exact_g2_extension_and_contract(self):
  r=read('macos-g2-result.json');b=read('macos-g2-build.json');host=read('macos-reference.json');self.assertTrue(r['ready']);self.assertEqual(len(r['observations']),241);self.assertFalse(r['mismatches']);self.assertFalse(r['missing_observations'])
  self.assertEqual(sha(HERE/'evidence/macos-g2-result.json'),probe.G2_REFERENCE_SHA256);self.assertEqual(r['guest_sha256'],baseline.GUEST_SHA);self.assertEqual(r['binary_sha256'],b['binary_sha256']);self.assertEqual(b['baseline_binary_sha256'],host['binary_sha256'])
  fixture=probe.contract.fixture((HERE.parent/'issue65-g2/g2_test.go.txt').read_bytes());pin=hashlib.sha256(fixture).hexdigest();self.assertEqual(r['fixture_sha256'],pin)
  expected=dict(host['source_inventory']);expected['cmd/issue65-wire/g2_test.go']=pin;self.assertEqual(b['source_inventory'],expected)
 def test_ownership_and_negative_scope(self):
  self.assertEqual(len(read('macos-timeout-native.json')['cases']),8)
  self.assertEqual(len(read('macos-timeout-controls.json')['cases']),5)
  negative=read('macos-timeout-native-controls.json');self.assertTrue(negative['original_source_restored']);self.assertEqual(len(negative['cases']),3);self.assertTrue(all(c['exit']!=0 for c in negative['cases']));self.assertEqual(negative['script_sha256'],sha(HERE/'timeout_native_controls.py'))
  self.assertEqual(len(read('macos-owner-native.json')['cases']),9);self.assertEqual(len(read('macos-lifecycle.json')['cases']),22)
  negatives=read('macos-native-controls.json');self.assertTrue(negatives['original_source_restored']);self.assertEqual(len(negatives['cases']),3);self.assertTrue(all(r['exit']!=0 for r in negatives['cases']));self.assertEqual(negatives['script_sha256'],sha(HERE/'native_controls.py'))
  self.assertEqual(read('macos-owner-controls.json')['source_sha256'],sha(ROOT/'internal/nativewire/owner.go'));self.assertEqual(read('macos-owner-controls.json')['test_sha256'],sha(ROOT/'internal/nativewire/owner_test.go'))
  self.assertEqual(len(read('macos-owner-controls.json')['cases']),8);self.assertEqual(len(read('controller-controls.json')['cases']),10)
 def test_timeout_source_and_public_contract(self):
  pins=json.loads((HERE/'timeout-source.json').read_text());self.assertEqual(pins['header_sha256'],sha(HERE/'deadline.h.txt'));self.assertEqual(read('controller-controls.json')['header_sha256'],pins['header_sha256']);self.assertEqual(read('controller-controls.json')['controller_sha256'],pins['controller_sha256'])
  host=read('macos-reference.json')
  for name in ('timeout.go','timeout_test.go'):self.assertEqual(host['source_inventory']['internal/nativewire/'+name],sha(ROOT/'internal/nativewire'/name))
  wire_patch=subprocess.check_output(['git','show',baseline.GUEST_SOURCE+':guest/experimental.patch'],cwd=ROOT);self.assertEqual(wire_patch,(ROOT/'guest/experimental.patch').read_bytes())
  self.assertEqual(read('macos-timeout-controls.json')['source_sha256'],sha(ROOT/'internal/nativewire/timeout.go'));self.assertEqual(read('macos-timeout-controls.json')['test_sha256'],sha(ROOT/'internal/nativewire/timeout_test.go'))
  self.assertIn('--- PASS: TestNativeTimeoutPublicDefaults',(HERE/'evidence/macos-public-timeout-contract.txt').read_text())
 def test_tooling_syntax(self):
  for p in HERE.glob('*.py'):compile(p.read_bytes(),str(p),'exec')
 def test_ci_uses_new_probe_and_fixed_origin(self):
  text=(ROOT/'.github/workflows/issue65-p1-timeout.yml').read_text();self.assertEqual(re.findall(r'^          ref: (\w+)$',text,re.M),[baseline.GUEST_SOURCE]*2)
  self.assertIn('branches: [experiment/issue65-p1-timeout]',text);self.assertIn('issue65-p1-timeout/probe.py runtime',text);self.assertIn('issue65-p1-timeout/probe_baseline.py',text)
  for name in ('probe.py','probe_baseline.py'):self.assertNotIn('PENDING_P1_',(HERE/name).read_text())
if __name__=='__main__':unittest.main()
