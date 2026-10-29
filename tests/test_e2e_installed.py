"""Consumer boundary oracles reject source fallback and incomplete case receipts."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / 'scripts'))
import e2e_installed as consumer


class TestInstalledController(unittest.TestCase):
    def test_python_staging_keeps_hooks_but_uses_default_host(self):
        source = (ROOT / 'docs/examples/e2e_owned/python/test_orders.py').read_text()
        staged = consumer.stage_python(source)
        self.assertIn('options={}', staged)
        self.assertNotIn('MARIAMEM_TEST_HOST', staged)
        self.assertNotIn('parents[4]', staged)
        self.assertIn('register(app)', staged)

    def test_changed_staging_anchors_reject(self):
        with self.assertRaises(ValueError): consumer.stage_python('other input')
        with self.assertRaises(ValueError): consumer.stage_go('other input')

    def test_go_staging_uses_copied_schema(self):
        source = (ROOT / 'docs/examples/e2e_owned/go/entry_test.go').read_text()
        staged = consumer.stage_go(source)
        self.assertIn('os.ReadFile("schema.sql")', staged)
        self.assertNotIn('../../../../', staged)

    def test_complete_census(self):
        rows = [dict(Action='pass', Test=n) for n in ('TestOwnedOrders', 'TestOwnedOrders/first', 'TestOwnedOrders/second')]
        text = '\n'.join(json.dumps(row) for row in rows)
        self.assertEqual(len(consumer.go_cases(text)), 3)
        for bad in [rows[:-1], rows + [dict(Action='fail', Test='other')], rows + [dict(Action='skip', Test='other')], rows + [dict(Action='pass', Test='extra')]]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                consumer.go_cases('\n'.join(json.dumps(row) for row in bad))

    def test_wheel_requires_receipt_and_current_sdk_bytes(self):
        import tempfile, zipfile, hashlib
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'tests/evidence').mkdir(parents=True)
            package = root / 'python/mariamem'; package.mkdir(parents=True)
            (package / 'e2e.py').write_text('current')
            wheel = root / 'sdk.whl'
            with zipfile.ZipFile(wheel, 'w') as archive:
                archive.writestr('mariamem/e2e.py', 'current')
            receipt = root / 'tests/evidence/alpha-wheel.json'
            receipt.write_text(json.dumps(dict(source_commit='source', sha256=hashlib.sha256(wheel.read_bytes()).hexdigest())))
            with patch.object(consumer, 'ROOT', root):
                consumer.wheel_source(wheel, 'source')
                with self.assertRaises(ValueError): consumer.wheel_source(wheel, 'wrong')
                (package / 'e2e.py').write_text('changed')
                with self.assertRaises(ValueError): consumer.wheel_source(wheel, 'source')

    def test_environment_removes_sdk_and_source_overrides(self):
        from unittest.mock import patch
        with patch.dict('os.environ', {'PYTHONPATH': 'source', 'MARIAMEM_HOST_BINARY': 'wrong', 'GH_TOKEN': 'secret'}):
            env = consumer.clean_env()
        self.assertNotIn('PYTHONPATH', env)
        self.assertNotIn('MARIAMEM_HOST_BINARY', env)
        self.assertNotIn('GH_TOKEN', env)


if __name__ == '__main__': unittest.main()
