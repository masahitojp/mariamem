"""Independent baseline contract: no selective removal or hidden guest diagnostics."""
from pathlib import Path
import sys
import json
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'benchmarks'))
from final_latency import summarize_trials, trial_command
import final_latency as benchmark


def trial(condition, latency, phase='measurement', exit_code=0):
    return {'phase': phase, 'condition': condition, 'exit_code': exit_code,
            'report': {'completed': not exit_code, 'samples': [
                {'case': 'fork_first_sql', 'per_db': [{'latency_seconds': latency}]}]}}


def test_distribution_keeps_slow_runs_and_separates_warmup_and_diagnostics():
    rows = [trial('production', value) for value in range(1, 21)]
    rows += [trial('production', 1000, 'warmup'), trial('attribution', 200)]
    result = summarize_trials(rows)
    assert result['production'] == {'count': 20, 'min': 1, 'p50': 10.5, 'p95': 19.05, 'max': 20}
    assert result['attribution']['p95'] == 200


def test_failure_cannot_be_filtered_to_claim_a_latency_verdict():
    with pytest.raises(ValueError, match='failed trial'):
        summarize_trials([trial('production', .4), trial('production', .6, exit_code=1)])


def test_each_child_measures_one_complete_fork_with_only_explicit_diagnostics():
    off = trial_command('runner', 'native', 'raw.json', 'production')
    on = trial_command('runner', 'native', 'raw.json', 'attribution')
    assert on == off + ['--guest-stage-timing']
    for flag, value in (('--runs', '1'), ('--warmup', '0'), ('--workers', '1'), ('--rows', '1000')):
        assert off[off.index(flag)+1] == value


@pytest.mark.parametrize('production_only,comparison', [(False,False),(True,False),(True,True)])
def test_supervisor_retains_fresh_child_reports_and_alternates_order(tmp_path, monkeypatch, production_only, comparison):
    native = tmp_path/'native'
    native.mkdir()
    (native/'manifest.json').write_text('{}')
    output = tmp_path/'results/report.json'
    control = tmp_path/'control'
    control.write_bytes(b'control')
    monkeypatch.setattr(benchmark, 'environment', lambda _: {'commit': 'sha', 'platform': 'test'})
    monkeypatch.setattr(benchmark, 'runner_metadata', lambda _: {'cpu': {'output': 'Model name: test-runner'}})
    monkeypatch.setattr(benchmark, 'validate_guest_timing', lambda _: None)
    monkeypatch.setattr(benchmark, 'summarize', lambda _: [])
    monkeypatch.setattr(benchmark, 'summarize_stages', lambda _: [])
    monkeypatch.setenv('MARIAMEM_TIMING_DIR', 'must-not-leak')
    commands = []
    def run(command, **kwargs):
        if command[0] == 'go':
            # The test uses an isolated output root, never a real built runner.
            Path(command[command.index('-o')+1]).write_bytes(b'runner')
        else:
            commands.append(command)
            assert 'MARIAMEM_TIMING_DIR' not in kwargs['env']
            report = trial('production', .6)['report']
            report['samples'][0]['phase'] = 'measurement'
            report['samples'][0]['workers'] = 1
            report['samples'][0]['latency_seconds'] = .6
            report['samples'][0]['per_db'][0]['stage_timings'] = {'host': {'guest': {}}}
            Path(command[command.index('--json')+1]).write_text(json.dumps(report))
        return SimpleNamespace(returncode=0)
    # Keep source paths real, but redirect the only repository build output.
    real_run = run
    def isolated_run(command, **kwargs):
        if command[0] == 'go':
            command = list(command)
            command[command.index('-o')+1] = str(tmp_path/'runner')
        return real_run(command, **kwargs)
    monkeypatch.setattr(benchmark.subprocess, 'run', isolated_run)
    monkeypatch.setattr(sys, 'argv', ['final_latency.py', '--native-dir', str(native),
                                    '--json', str(output), '--runs', '20'] + (['--production-only'] if production_only else []) + (['--comparison-runner',str(control)] if comparison else []))
    # Hashing refers to the standard binary path; supply only that one read.
    original_read = Path.read_bytes
    monkeypatch.setattr(Path, 'read_bytes', lambda path: b'runner' if path == benchmark.ROOT/'build/bench/isolation-go'
                        else original_read(path))
    benchmark.main()
    result = json.loads(output.read_text())
    expected = 22 if production_only and not comparison else 44
    assert result['completed'] and len(result['trials']) == expected
    assert result['distribution']['production']['count'] == 20
    assert result['distribution']['production']['max'] == .6
    assert ['--guest-stage-timing' in command for command in commands[:4]] == ([False]*4 if production_only else [False, True, True, False])
    assert len({command[command.index('--json')+1] for command in commands}) == expected
    assert result['runner_metadata']['cpu']['output'] == 'Model name: test-runner'
    if comparison:
        assert result['distribution']['control']['count'] == 20
        assert [Path(c[0]) == control for c in commands[:4]] == [True,False,False,True]
        assert result['comparison_runner_sha256'] != result['runner_sha256']
