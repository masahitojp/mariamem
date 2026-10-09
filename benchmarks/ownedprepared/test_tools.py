"""Deterministic evidence/gate checks; no MariaDB execution or benchmarks."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
MODULE=Path(__file__).parent
SHA='a'*40


def load_runner():
    spec=importlib.util.spec_from_file_location('candidate_runner',ROOT/'scripts/validate_product_candidate.py')
    module=importlib.util.module_from_spec(spec)
    sys.path.insert(0,str(ROOT/'scripts'))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


class EvidenceToolsTest(unittest.TestCase):
    def test_annotated_release_tag_is_distinct_from_the_pinned_source_commit(self):
        module=load_runner()
        with tempfile.TemporaryDirectory() as temporary:
            repository=Path(temporary)
            def git(*args):
                return subprocess.check_output(['git','-C',str(repository),
                    '-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
                    '-c','commit.gpgsign=false','-c','tag.gpgsign=false',*args],text=True).strip()
            git('init','-q')
            (repository/'source').write_text('released\n')
            git('add','source');git('commit','-qm','released')
            commit=git('rev-parse','HEAD')
            git('tag','-a','v0.4.3','-m','published')
            tag=git('rev-parse','refs/tags/v0.4.3')
            self.assertNotEqual(tag,commit)
            from git_identity import ReleasePin, verify_release_pin
            def verify(tag_object,source_commit):
                return verify_release_pin(repository,ReleasePin('v0.4.3',tag_object,source_commit)).source_commit
            self.assertEqual(verify(tag,commit),commit)
            # Reproduce the CI bug: a tag object cannot be the expected commit.
            with self.assertRaisesRegex(ValueError,'must be distinct'):
                verify(tag,tag)
            (repository/'source').write_text('later source\n')
            git('commit','-qam','later')
            with self.assertRaisesRegex(ValueError,'pinned release commit'):
                verify(tag,git('rev-parse','HEAD'))
            with self.assertRaisesRegex(ValueError,'annotated tag object'):
                verify(commit,git('rev-parse','HEAD'))

    def test_comparison_rejects_failed_and_other_candidate_gates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            gate=root/'gate.json'
            argv=[sys.executable,str(MODULE/'run_compare.py'),'--baseline-root',str(root),
                  '--baseline-bench','never-executed','--candidate-bench','never-executed',
                  '--baseline-host','never-executed','--candidate-host','never-executed',
                  '--helper','never-executed','--scratch',str(root/'scratch'),'--out',str(root/'out'),
                  '--correctness-evidence',str(gate),'--candidate-sha',SHA]
            for result,candidate in [('FAIL',SHA),('PASS','b'*40)]:
                gate.write_text(json.dumps(dict(result=result,candidate_sha=candidate)))
                process=subprocess.run(argv,capture_output=True,text=True)
                self.assertNotEqual(process.returncode,0)
                self.assertIn('correctness gate is not PASS',process.stderr)
                self.assertFalse((root/'out').exists())

    def test_summary_requires_complete_trials_and_keeps_parallel_wall_distinct(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary)
            cases=[('serial',size) for size in (0,10,100)]+[('crud',0),('application',0),('parallel',10),('fdscale',0)]
            for boundary in ('go','import'):
                for case,size in cases:
                    for label in ('baseline','candidate'):
                        for trial in range(1 if case=='fdscale' else 3):
                            data=dict(workers=4 if case=='parallel' else 1,
                                      operations=[dict(name=f'fork_ready_{index:02}',seconds=.1) for index in range(16)],
                                      suite_cpu_seconds=2.,suite_cpu_scope='self' if boundary=='go' else 'self+reaped children; diagnostics included',
                                      suite_seconds=2.,suite_operation_seconds=4.,
                                      suite_product_seconds=1.8,diagnostic_overhead_seconds=.2)
                            (base/f'{boundary}-{case}-{size}-{trial}-{label}.json').write_text(json.dumps(data))
            for size in (0,10,100):
                for label in ('baseline','candidate'):
                    for trial in range(3):
                        data=dict(operations=[dict(name=name,seconds=.1) for name in ('import','source_ready','snapshot','snapshot_persisted')],
                                  suite_product_seconds=.5,suite_cpu_seconds=.2,suite_cpu_scope='self+reaped children; diagnostics included')
                        (base/f'import-capture-{size}-{trial}-{label}.json').write_text(json.dumps(data))
            argv=[sys.executable,str(MODULE/'summarize.py'),'--input',str(base),'--out',str(base/'reduced')]
            subprocess.run(argv,check=True,capture_output=True)
            rows=json.loads((base/'reduced/summary.json').read_text())
            self.assertEqual(len(rows),24)
            parallel=next(row for row in rows if row['case']=='parallel')
            self.assertEqual(parallel['fork_samples'],48)
            self.assertEqual(parallel['suite_product_p50_s'],1.8)
            self.assertEqual(parallel['sum_operation_p50_s'],4.)
            python_parallel=next(row for row in rows if row['case']=='parallel' and row['boundary']=='import')
            self.assertIn('diagnostics included',python_parallel['suite_cpu_scope'])
            (base/'go-serial-0-0-baseline.json').unlink()
            result=subprocess.run(argv,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('missing trials',result.stderr)


if __name__=='__main__':
    unittest.main()
