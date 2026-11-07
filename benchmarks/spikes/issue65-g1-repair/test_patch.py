"""Source seam guards, complementing the real guest/native runtime observations."""
from pathlib import Path
import re
import unittest
ROOT=Path(__file__).resolve().parents[3]
PATCH=(ROOT/'guest/experimental.patch').read_text()
def sections(name):
    return '\n'.join(re.findall(r'(?ms)^--- [^\n]+\n\+\+\+ b/'+re.escape(name)+r'\n(.*?)(?=^--- |\Z)',PATCH))
class RepairGuards(unittest.TestCase):
    def test_rejection_before_dispatch_and_alias_invalidation(self):
        p=sections('sql/sql_parse.cc')
        self.assertLess(p.index('thd->clear_last_stmt();'),p.index('packet_length == 0'))
        self.assertIn('command == COM_SET_OPTION && packet_length != 2',p)
        self.assertIn('packet_length > 1048576',p)
    def test_native_parser_retains_d2_and_checks_consumption(self):
        p=sections('sql/sql_prepare.cc')
        self.assertIn('get_wire_param_length(pos, len, true)',p)
        self.assertIn('if (consume_overdeclared_string)',p)
        guard='stmt->thd->mariamem_native_wire && read_pos != data_end'
        added='\n'.join(line[1:] for line in p.splitlines() if line.startswith('+'))
        removed='\n'.join(line[1:] for line in p.splitlines() if line.startswith('-'))
        if 'mariamem_wire_null_fallback' in added:
            # G2 replaces both original guards with the Human-approved native
            # NULL fallback condition;removed patch lines are not active code.
            self.assertEqual(2,added.count(guard));self.assertEqual(2,removed.count(guard))
            self.assertEqual(2,added.count('mariamem_native_wire && !native_null_fallback &&'))
        else:
            self.assertEqual(2,added.count(guard)-removed.count(guard))
        self.assertIn('uint4korr(packet + 5) != 1',p)
        self.assertIn('packet_end != packet && packet[0] > 1',p)
    def test_restore_all_descriptors_after_native_decode_failure(self):
        p=sections('sql/sql_prepare.cc');a=p.index('param_array[i]->mariamem_save_conversion');b=p.index('res= (setup_conversion_functions',a);c=p.index('if (res && saved)',b);d=p.index('param_array[i]->mariamem_restore_conversion',c)
        self.assertLess(a,b);self.assertLess(b,c);self.assertLess(c,d)
        h=sections('sql/item.h')
        for field in ('handler','value_handler','is_unsigned','simple','empty_string_is_null'):
            self.assertIn(field,h)
    def test_saved_native_pass_and_reference_pins(self):
        import hashlib,json,importlib.util
        folder=Path(__file__).resolve().parent
        spec=importlib.util.spec_from_file_location('g1_repair_probe',folder/'probe.py')
        probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
        evidence=folder/'evidence'
        result=probe.g1.analyze((evidence/'macos-g1-raw.txt').read_text(),0)
        self.assertEqual(result,json.loads((evidence/'macos-g1-result.json').read_text()))
        self.assertTrue(result['ready']);self.assertEqual(234,len(result['observations']))
        reference=evidence/'macos-reference.json';ref=json.loads(reference.read_text())
        self.assertEqual(probe.SOURCE_REFERENCE_SHA256,hashlib.sha256(reference.read_bytes()).hexdigest())
        self.assertEqual(probe.GUEST_SHA,ref['guest_sha256'])
        self.assertEqual(probe.GUEST_SOURCE,ref['guest_source_commit'])
        self.assertEqual(probe.HOST_SOURCE,ref['host_source_commit'])
        self.assertEqual(probe.GUEST_SHA,json.loads((folder/'binding/identity.json').read_text())['guest_sha256'])
        self.assertEqual(39,len(ref['repaired_g1_observations']))
        workflow=(ROOT/'.github/workflows/issue65-compat-fixes.yml').read_text()
        self.assertEqual(2,workflow.count('ref: '+probe.GUEST_SOURCE))

    def test_capture_debt_fixture_only_adds_idle_before_injection(self):
        import importlib.util,hashlib,json
        folder=Path(__file__).resolve().parent
        spec=importlib.util.spec_from_file_location('idle_fix_probe',folder/'probe.py')
        probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
        raw=(folder.parent/'issue65-native-capture/capture_test.go.txt').read_bytes()
        corrected=probe.prepared_capture_fixture(raw)
        self.assertEqual(raw,corrected.replace(b'\tdefer rd.Close()\n\tidle(t, r)\n\tr.failAcquisition',b'\tdefer rd.Close()\n\tr.failAcquisition',1))
        self.assertEqual(probe.CAPTURE_FIXTURE_AFTER,hashlib.sha256(corrected).hexdigest())
        with self.assertRaises(ValueError):probe.prepared_capture_fixture(raw+b'\n')
        ref=json.loads((folder/'evidence/macos-reference.json').read_text())['source_inventory']
        adjusted=probe.adjusted_capture_reference(ref)
        self.assertEqual({probe.CAPTURE_FIXTURE_NAME}, {k for k in ref.keys()|adjusted.keys() if ref.get(k)!=adjusted.get(k)})
        with self.assertRaises(ValueError):probe.adjusted_capture_reference(adjusted)

    def test_unchanged_observation_fixture(self):
        import hashlib
        p=ROOT/'benchmarks/spikes/issue65-prepared-input/g1_test.go.txt'
        self.assertEqual('804f48fa64a4467a879c3fcd65eb14b6a2b8dda53cf4bade570e163eabc0fd77',hashlib.sha256(p.read_bytes()).hexdigest())
if __name__=='__main__':unittest.main()
