"""E2E selector/gates must not skip owned entry changes or revive auto-full CI."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from live_selection import FAMILIES, select, main


class TestE2ESelection(unittest.TestCase):
    def test_e2e_inputs_and_shared_inputs_select(self):
        for path in ['python/mariamem/e2e.py', 'mariamemtest/http.go',
                     'mariamemtest/http_jobs_runtime_test.go', 'docs/examples/e2e_owned/python/test_retirement.py',
                     'scripts/e2e_installed.py', 'scripts/e2e_workflow_timing.py',
                     'tests/test_e2e_entry.py', 'tests/test_e2e_decision.py', 'tests/test_e2e_installed.py',
                     'internal/live/endpoint.go', 'python/mariamem/__init__.py', 'unknown.py']:
            with self.subTest(path=path): self.assertTrue(select([path], 'pull_request')['e2e'])

    def test_unrelated_docs_and_known_other_entry_do_not_select(self):
        for paths in [['docs/development.md'], ['mariamemtest/fixture.go'], ['python/mariamem/pytest_plugin.py']]:
            self.assertFalse(select(paths, 'pull_request')['e2e'])
            self.assertTrue(select(paths+['python/mariamem/e2e.py'], 'pull_request')['e2e'])

    def test_manual_unknown_and_unavailable_diff_keep_full(self):
        for event in ['workflow_dispatch', 'unknown']:
            self.assertTrue(all(select(['README.md'], event).values()))
        self.assertTrue(select([], 'pull_request')['e2e'])
        self.assertTrue(select(['README.md'], 'pull_request', 'event base unavailable')['e2e'])

    def test_both_owned_steps_are_gated_and_manual_policy_retained(self):
        text = (ROOT/'.github/workflows/live-host.yml').read_text()
        for name in ['Owned E2E entry component and actual application checks', 'Installed owned E2E entry outside the source checkout']:
            self.assertIn('- name: '+name+"\n        if: steps.families.outputs.e2e == 'true'", text)
        self.assertIn('id: families', text)
        self.assertIn('python scripts/live_selection.py --github-output', text)
        self.assertIn('  workflow_dispatch:', text)
        self.assertNotIn('  pull_request:', text)
        self.assertNotIn('  push:', text)

    def test_manual_output_exports_all_registered_families(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'output'
            with patch.dict(os.environ, GITHUB_EVENT_NAME='workflow_dispatch', GITHUB_OUTPUT=str(output)), patch.object(sys, 'argv', ['live_selection.py', '--github-output']):
                main()
            self.assertEqual(set(output.read_text().splitlines()), {name+'=true' for name in FAMILIES})

    def test_release_notes_keep_both_candidate_announcements(self):
        text = (ROOT/'docs/release-notes/unreleased.md').read_text()
        for text_required in ['Python prepared entry (P1)', 'PrepareCommand',
                              'Owned E2E entry candidate', 'BrowserEntry', 'NewHTTP/Case(t)']:
            self.assertIn(text_required, text)
