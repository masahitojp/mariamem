"""Focused provenance, reader and historical-context preservation checks."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('evidence_normalization', HERE / 'normalize.py')
n = importlib.util.module_from_spec(spec)
spec.loader.exec_module(n)


def without_buildinfo(value):
    if isinstance(value, dict):
        return {k: without_buildinfo(v) for k, v in value.items() if k != 'go_buildinfo'}
    if isinstance(value, list):
        return [without_buildinfo(v) for v in value]
    return value


class Preservation(unittest.TestCase):
    def test_raw_recipe_and_normalized_hashes(self):
        self.assertEqual(n.verify(), 6)
        for row in json.loads(n.RECEIPT.read_text())['files']:
            raw = n.raw_bytes(row['path'])
            actual = (n.ROOT / row['path']).read_bytes()
            self.assertEqual(len(raw), row['raw_bytes'])
            self.assertEqual(len(actual), row['normalized_bytes'])
            if row['path'].endswith('.json'):
                # Includes every measurement/assertion and all historical inventories.
                self.assertEqual(without_buildinfo(json.loads(raw)),
                                 without_buildinfo(json.loads(actual)), row['path'])
            else:
                before, after = raw.splitlines(), actual.splitlines()
                self.assertEqual(before[:1] + before[2:], after[:1] + after[2:])
                self.assertIn(b'SyntaxError: unterminated string literal', actual)

    def test_raw_pin_consumers_and_historical_inventories(self):
        for row in json.loads(n.RECEIPT.read_text())['files']:
            path = Path(row['path'])
            if path.name == 'macos-reference.json':
                reader = n.ROOT / path.parent.parent / 'probe_baseline.py'
                self.assertIn("SOURCE_REFERENCE_SHA256='" + row['normalized_sha256'] + "'",
                              reader.read_text())
                # Pin replacement is the only change to either executable reader.
                expected = n.raw_bytes(reader.relative_to(n.ROOT).as_posix()).replace(
                    row['raw_sha256'].encode(), row['normalized_sha256'].encode())
                self.assertEqual(reader.read_bytes(), expected)
            # The C2 historical public source inventory deliberately retains raw pins.
            inventory = json.loads((n.ROOT / 'benchmarks/spikes/issue65-p1-public/evidence/public-source.json').read_text())
            self.assertEqual(inventory['source_inventory'][row['path']], row['raw_sha256'])

    def test_historical_fail_records_and_other_evidence_unchanged(self):
        # Protect every existing owner/timeout/core/public evidence record, including
        # the historical FAIL receipts, except the six explicitly normalized files.
        changed = {row['path'] for row in json.loads(n.RECEIPT.read_text())['files']}
        for spike in ('owner', 'timeout', 'core', 'public'):
            directory = f'benchmarks/spikes/issue65-p1-{spike}/evidence'
            names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', n.BASE, directory],
                                            cwd=n.ROOT, text=True).splitlines()
            for name in names:
                if name not in changed:
                    self.assertEqual((n.ROOT / name).read_bytes(), n.raw_bytes(name), name)

    def test_recipe_rejects_missing_or_duplicate_paths(self):
        rows = json.loads(n.RECEIPT.read_text())['files']
        for row in (rows[0], rows[3]):
            raw = n.raw_bytes(row['path'])
            with self.assertRaises(ValueError):
                n.normalize(row['path'], n.normalize(row['path'], raw))
            with self.assertRaises(ValueError):
                n.normalize(row['path'], raw + raw)

    def test_guard_implementation_unchanged(self):
        self.assertEqual((n.ROOT / 'scripts/check_public.py').read_bytes(),
                         n.raw_bytes('scripts/check_public.py'))


if __name__ == '__main__':
    unittest.main()
