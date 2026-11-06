"""Deterministic acceptance guards; no builder, network or runtime in these tests."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('linux_probe',Path(__file__).with_name('probe.py'))
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)

class AcceptanceGuards(unittest.TestCase):
    def test_native_bootstrap_failure_text_is_a_valid_negative_case(self):
        log='FAIL:product fresh/restore bootstrap\n--- PASS: TestRestore (0.1s)\nPASS\n'
        self.assertEqual(probe.cases_from_log(log,{'TestRestore'}),[('TestRestore','0.1s')])

    def test_missing_or_duplicated_case_is_not_pass(self):
        for log in ['--- PASS: TestA (0.1s)\nPASS\n','--- PASS: TestA (0.1s)\n--- PASS: TestA (0.2s)\nPASS\n']:
            with self.assertRaises(ValueError):probe.cases_from_log(log,{'TestA','TestB'})

    def test_failed_or_incomplete_run_is_not_pass(self):
        for log in ['--- PASS: TestA (0.1s)\nFAIL\n','--- PASS: TestA (0.1s)\n','--- FAIL: TestB (0.1s)\n--- PASS: TestA (0.1s)\nPASS\n']:
            with self.assertRaises(ValueError):probe.cases_from_log(log,{'TestA'})

    def test_extra_go_source_and_changed_data_are_detected(self):
        reference={'code/main.go':'a','code/data.bin':'b','provenance.json':'mac'}
        count,diff=probe.source_difference({**reference,'code/extra.go':'new'},reference)
        self.assertEqual(count,2);self.assertEqual(diff,['code/extra.go'])
        self.assertEqual(probe.source_difference({**reference,'code/data.bin':'changed'},reference)[1],['code/data.bin'])

    def test_host_provenance_may_differ_but_code_may_not(self):
        reference={'code/main.go':'a','code/data.bin':'b','provenance.json':'mac'}
        self.assertEqual(probe.source_difference({**reference,'provenance.json':'linux'},reference),(2,[]))
        self.assertEqual(probe.source_difference({**reference,'code/main.go':'different'},reference)[1],['code/main.go'])

    def test_guest_mismatch_is_saved_and_never_refreshes_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            w=Path(tmp);(w/'temp/artifact').mkdir(parents=True);(w/'evidence').mkdir()
            record={'result':'UNQUALIFIED','source_commit':probe.GUEST_SOURCE,'guest_sha256':probe.GUEST_SHA}
            (w/'temp/artifact/guest.json').write_text(json.dumps(record));(w/'temp/artifact/mariamem.wasm').write_bytes(b'wrong guest')
            original=probe.GUEST_SHA
            with self.assertRaises(ValueError):probe.guest_record(w)
            self.assertEqual(probe.GUEST_SHA,original)
            self.assertEqual((w/'evidence/unexpected-guest.wasm').read_bytes(),b'wrong guest')
            self.assertEqual(json.loads((w/'temp/artifact/guest.json').read_text()),record)

    def test_root_builder_scopes_git_trust_before_source_inspection(self):
        class StopBeforeMount(Exception):pass
        with tempfile.TemporaryDirectory() as tmp:
            w=Path(tmp);(w/'experiment.json').write_text(json.dumps({'repo':str(w/'source')}))
            with patch.dict(os.environ,{},clear=True),patch.object(probe.platform,'system',return_value='Linux'),patch.object(probe.platform,'machine',return_value='aarch64'),patch.object(probe.os,'geteuid',return_value=0),patch.object(probe,'identity',side_effect=StopBeforeMount):
                with self.assertRaises(StopBeforeMount):probe.build(w)
                self.assertEqual(os.environ['GIT_CONFIG_COUNT'],'2')
                self.assertEqual(os.environ['GIT_CONFIG_VALUE_0'],str(w/'worktree'))
                self.assertEqual(os.environ['GIT_CONFIG_VALUE_1'],str(w/'source'))

    def test_runtime_does_not_run_on_mac(self):
        with patch.object(probe.platform,'system',return_value='Darwin'),patch.object(probe,'guest_record') as record:
            with self.assertRaises(ValueError):probe.runtime(Path('/not-a-workspace'))
            record.assert_not_called()

if __name__=='__main__':unittest.main()
