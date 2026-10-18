"""Offline fail-closed checks using recorded product cells, not guest execution."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('current_product', ROOT/'benchmarks/current-product/run.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CurrentProductPerformanceTest(unittest.TestCase):
    def recorded(self, language):
        name = f'baseline-{language}-light-0-fork.json'
        data = json.loads((ROOT/'benchmarks/main-product-evidence/results/matrix'/name).read_text())
        cell = dict(version='v0.5.0', language=language, mode='fork', case='light', trial=0,
                    size=0, tables=1, workers=1, count=4, pilot=False)
        return cell, data

    def test_plan_is_finite_and_does_not_reopen_large_fresh(self):
        cells = MODULE.plan()
        self.assertEqual(len(cells), 92)
        self.assertEqual(sum(c['pilot'] for c in cells), 8)
        self.assertEqual(len({MODULE.cell_name(c) for c in cells}), 92)
        self.assertFalse(any(c['size'] == 100 and c['mode'] == 'fresh' for c in cells))
        for version in MODULE.VERSIONS:
            self.assertEqual(sum(c['version'] == version and not c['pilot'] for c in cells), 42)

    def test_export_adapter_does_not_hide_other_observer_changes(self):
        before = 'start\nSnapshotOptions{Destination: *export}\nend\n'
        after = 'start\n' + MODULE.EXPORT_GUARD + 'SnapshotOptions{}\nend\n'
        self.assertEqual(MODULE.normalize_observer(before), MODULE.normalize_observer(after))
        self.assertNotEqual(MODULE.normalize_observer(before), MODULE.normalize_observer(after.replace('end', 'different SQL')))

    def test_go_rejects_wrong_platform_source_and_unreleased_mapping(self):
        cell, data = self.recorded('go')
        source = data['label']
        MODULE.reduce_cell(cell, data, source)
        invalid = copy.deepcopy(data)
        invalid.update(goos='linux', goarch='amd64')
        with self.assertRaises(AssertionError): MODULE.reduce_cell(cell, invalid, source)
        with self.assertRaises(AssertionError): MODULE.reduce_cell(cell, data, '0'*40)
        invalid = copy.deepcopy(data)
        invalid['resources']['after_go']['linear_memory_virtual']['active_mappings'] = 1
        with self.assertRaises(AssertionError): MODULE.reduce_cell(cell, invalid, source)

    def test_python_rejects_incomplete_and_missing_child_oracles(self):
        cell, data = self.recorded('python')
        source = data['source_commit']
        MODULE.reduce_cell(cell, data, source)
        for mutate in (lambda d:d.update(completed=False), lambda d:d['samples'].pop(),
                       lambda d:d['samples'][0].update(server_version='13.1.0'),
                       lambda d:d.update(source_commit='0'*40)):
            invalid = copy.deepcopy(data);mutate(invalid)
            with self.assertRaises(AssertionError):MODULE.reduce_cell(cell, invalid, source)

    def test_summary_rejects_missing_or_duplicate_cells(self):
        with self.assertRaises(AssertionError):MODULE.summarize([])
        rows = [{**c, 'name':MODULE.cell_name(c), 'wall_seconds':1.0} for c in MODULE.plan()]
        self.assertEqual(len(MODULE.summarize(rows)), 14)
        rows[-1] = rows[0]
        with self.assertRaises(AssertionError):MODULE.summarize(rows)


if __name__ == '__main__':unittest.main()
