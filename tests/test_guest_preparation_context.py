"""Selected input storage/isolation boundaries; actual sources use the comparison recipe."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import guest_preparation_context as context
from common import fetch
from prepared_source_patch import inputs as proof_inputs


class PreparationContextTests(unittest.TestCase):
    def test_three_profiles_resolve_and_keep_stage_contract(self):
        for engine, profile in [('12.3.3', 'legacy-full'), ('13.0.2', 'legacy-full'), ('13.0.2', 'native-text'), ('13.2.0', 'native-text')]:
            result = context.resolve(ROOT, engine, profile)
            self.assertEqual(result['stages'], context.stage_order(result['guest_input']))
            self.assertEqual(result['guest_input']['version'], engine)

    def test_existing_output_is_never_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'marker'
            marker.write_text('preserve')
            with self.assertRaises(FileExistsError):
                context.prepare_selected(ROOT, '12.3.3', 'legacy-full', directory)
            self.assertEqual(marker.read_text(), 'preserve')

    def test_symlink_input_even_inside_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'real').mkdir()
            (root / 'real/data').write_text('data')
            (root / 'alias').symlink_to(root / 'real', target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                context.read_input(root, 'alias/data')

    def test_output_cannot_overlap_maintained_inputs(self):
        with self.assertRaisesRegex(ValueError, 'overlaps'):
            context.prepare_selected(ROOT, '12.3.3', 'legacy-full', ROOT / 'guest/never-created')
        self.assertFalse((ROOT / 'guest/never-created').exists())

    def test_mixed_selection_fails_before_output_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'output'
            with self.assertRaisesRegex(ValueError, 'unregistered'):
                context.prepare_selected(ROOT, '12.3.3', 'native-text', target)
            self.assertFalse(target.exists())

    def test_explicit_fetch_uses_selected_lock_and_rejects_cache_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            downloads = Path(directory)
            (downloads / 'archive').write_bytes(b'right')
            lock = {'inputs': [{'name': 'mariadb', 'file': 'archive', 'url': 'invalid:',
                                'sha256': hashlib.sha256(b'right').hexdigest()}]}
            self.assertEqual(fetch('mariadb', lock=lock, downloads=downloads).read_bytes(), b'right')
            (downloads / 'archive').write_bytes(b'wrong')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                fetch('mariadb', lock=lock, downloads=downloads)

    def test_all_corrected_proofs_and_selected_inputs_reach_common_pipeline(self):
        for engine, profile in [('12.3.3', 'legacy-full'), ('13.0.2', 'legacy-full'), ('13.0.2', 'native-text'), ('13.2.0', 'native-text')]:
            with tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / 'run'
                def pipeline(view, lock, work, fetch_input, *, selected):
                    self.assertEqual(selected['version'], engine)
                    self.assertEqual(lock, json.loads((view / 'release/inputs.lock.json').read_text()))
                    pin = proof_inputs(view)
                    self.assertEqual(pin.get('profile', 'legacy-full'), profile)
                    if profile == 'native-text':
                        self.assertEqual(len(pin['files']), 3)
                        self.assertIn('time_source_fixture', pin)
                    return {'release_eligible': False}
                with patch('prepare_guest.prepare', side_effect=pipeline), patch.object(context.subprocess, 'check_output', return_value='experiment/test\n'):
                    result = context.prepare_selected(ROOT, engine, profile, target)
                self.assertFalse(result['release_eligible'])
                self.assertEqual(result['selection'], engine + '/' + profile)

    def test_native_overlay_rejects_main(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(context.subprocess, 'check_output', return_value='main\n'):
            target = Path(directory) / 'run'
            with self.assertRaisesRegex(ValueError, 'experiment/'):
                context.prepare_selected(ROOT, '13.0.2', 'native-text', target)
            self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
