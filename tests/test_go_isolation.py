"""Thin launcher contract; fake process boundaries, no guest or artifact build."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'benchmarks'))
import go_isolation as benchmark


def test_native_input_is_explicit(monkeypatch):
    monkeypatch.delenv('MARIAMEM_NATIVE_DIR', raising=False)
    monkeypatch.setattr(sys, 'argv', ['go_isolation.py'])
    with pytest.raises(SystemExit) as error:
        benchmark.main()
    assert error.value.code == 2


@pytest.mark.parametrize('exit_code', [0, 1])
def test_launcher_preserves_raw_case_summary_failure_and_native_identity(tmp_path, monkeypatch, capsys, exit_code):
    root = tmp_path
    files = ['go_isolation.py', 'isolation_baseline.py', '_common.py', 'stage_report.py']
    (root/'benchmarks/goisolation').mkdir(parents=True)
    for name in files:
        (root/'benchmarks'/name).write_text('fixture')
    (root/'benchmarks/goisolation/main.go').write_text('fixture')
    native = root/'native'; native.mkdir()
    (native/'manifest.json').write_text('{"package_version":"test","sha256":{"mariamem.wasmu":"test-hash"}}')
    output = root/'benchmarks/results/report.json'
    monkeypatch.setattr(benchmark, 'ROOT', root)
    monkeypatch.setattr(benchmark, 'RESULTS', output.parent)
    monkeypatch.setattr(benchmark, '__file__', str(root/'benchmarks/go_isolation.py'))
    monkeypatch.setattr(benchmark, 'environment', lambda args: {'commit': 'test-sha', 'python': 'test-python'})
    monkeypatch.setattr(benchmark.subprocess, 'check_output', lambda *args, **kwargs: 'mysql test-version')
    commands = []
    def run(command, **kwargs):
        commands.append(command)
        if command[0] == 'go':
            Path(command[command.index('-o')+1]).write_bytes(b'runner')
            return SimpleNamespace(returncode=0)
        assert command[command.index('--workers')+1] == '1,4,8'
        assert command[command.index('--native-dir')+1] == str(native)
        Path(command[command.index('--json')+1]).write_text(json.dumps({
            'api': 'go', 'completed': exit_code == 0, 'environment': {'go': 'test-go'},
            'samples': [{'case': 'fork_first_sql', 'workers': 4, 'phase': 'measurement',
                         'latency_seconds': 2, 'per_db': [{'latency_seconds': 1}]}]}))
        return SimpleNamespace(returncode=exit_code)
    monkeypatch.setattr(benchmark.subprocess, 'run', run)
    monkeypatch.setattr(sys, 'argv', ['go_isolation.py', '--native-dir', str(native), '--json', str(output), '--runs', '20'])
    if exit_code:
        with pytest.raises(SystemExit) as error:
            benchmark.main()
        assert error.value.code == exit_code
    else:
        benchmark.main()
    result = json.loads(output.read_text())
    assert result['summary'][0]['p50_seconds'] == 2
    assert result['summary'][0]['per_db_p50_seconds'] == 1
    assert result['api'] == 'go' and result['completed'] == (exit_code == 0)
    assert result['environment']['native_manifest']['sha256']['mariamem.wasmu'] == 'test-hash'
    assert result['environment']['commit'] == 'test-sha'
    assert len(commands) == 2 and result['settings']['runs'] == 20


def test_paired_comparison_rejects_different_runtime_and_settings():
    import copy
    from compare_baselines import compare
    report = {'api': 'go', 'completed': True, 'environment': {'commit': 'sha', 'platform': 'mac', 'machine': 'arm64',
              'native_manifest': {'sha256': {name: 'same' for name in ['wasmer-headless', 'mariamem.wasmu', 'mariamem.wasmu.json']}}},
              'settings': {'runs': 20, 'workers': [1,4,8]},
              'summary': [{'case': 'start_first_sql', 'workers': 1, 'count': 20, 'p50_seconds': 1, 'p95_seconds': 2}]}
    python = copy.deepcopy(report); python['api'] = 'python'
    assert '1000.000 / 2000.000' in compare(report, python)
    changed = copy.deepcopy(python)
    changed['environment']['native_manifest']['sha256']['mariamem.wasmu'] = 'different'
    with pytest.raises(ValueError, match='identical mariamem.wasmu'):
        compare(report, changed)
    changed = copy.deepcopy(python)
    changed['settings']['runs'] = 10
    with pytest.raises(ValueError, match='matching setting runs'):
        compare(report, changed)
