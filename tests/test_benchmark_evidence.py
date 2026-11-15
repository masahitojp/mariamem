"""Evidence budgets preserve observations and reject storage growth/relocation."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import check_benchmark_evidence as guard
from layout import BENCHMARKS


def entry(n, identity='a'):
    return (n, identity)


def test_existing_main_and_compact_records():
    baseline = guard.tree(str(guard.ROOT), guard.BASELINE)
    result = guard.evaluate(baseline, baseline, baseline)
    assert result['totals']['benchmarks/'] == {'files': 2027, 'bytes': 27364485}
    assert guard.evaluate({'benchmarks/sample.json': entry(100)}, {}, {})['passed']


@pytest.mark.parametrize('path', ['benchmarks/log-build.txt', 'benchmarks/new.py',
                                 'docs/reviews/moved.json', 'docs/benchmarks/moved.json'])
def test_new_large_payload_cannot_hide_by_name_or_location(path):
    with pytest.raises(ValueError, match='oversized'):
        guard.evaluate({path: entry(guard.FILE_BYTES + 1)}, {}, {})


def test_many_small_records():
    with pytest.raises(ValueError, match='changed evidence'):
        guard.evaluate({f'benchmarks/{i}.json': entry(1) for i in range(51)}, {}, {})


def test_total_changed_bytes_not_net_delta():
    old = {'benchmarks/old.json': entry(2_000_000)}
    new = {f'benchmarks/{i}.json': entry(220_000) for i in range(5)}
    with pytest.raises(ValueError, match='changed evidence'):
        guard.evaluate(new, old, old)


@pytest.mark.parametrize('change', ['grow', 'same-size-edit', 'rename'])
def test_old_large_exception_is_identity_and_path_bound(change):
    old = {'benchmarks/large.json': entry(300_000)}
    if change == 'rename':
        new = {'benchmarks/renamed.json': entry(300_000)}
    else:
        new = {'benchmarks/large.json': entry(300_001 if change == 'grow' else 300_000, 'b')}
    with pytest.raises(ValueError, match='oversized'):
        guard.evaluate(new, old, old)


def test_split_prs_cannot_evade_cumulative_cap(monkeypatch):
    monkeypatch.setattr(guard, 'CAPS', {'benchmarks/': (10, 200)})
    first = {'benchmarks/1.json': entry(150)}
    assert guard.evaluate(first, {}, {})['passed']
    with pytest.raises(ValueError, match='cumulative'):
        guard.evaluate({**first, 'benchmarks/2.json': entry(150)}, {}, first)


def test_missing_or_non_commit_base_fails():
    with pytest.raises(Exception):
        guard.tree(str(guard.ROOT), '0' * 40)
    with pytest.raises(ValueError, match='exact commit'):
        guard.tree(str(guard.ROOT), 'HEAD')


def test_scope_keeps_code_and_provenance_conservative():
    import development_scope as scope
    assert scope.boundary('benchmarks/timer-product/summary.json') == 'docs'
    assert scope.boundary('benchmarks/new.json') == 'runtime'
    assert scope.boundary('benchmarks/modelcase/app.go') == 'runtime'
    assert scope.boundary(guard.PROVENANCE) == 'runtime'
    assert scope.boundary('benchmarks/main-product-evidence/results/matrix/basic.json') == 'runtime'
    assert scope.boundary('benchmarks/ucapreparedinput/input.json') == 'runtime'
    assert scope.select(['benchmarks/timer-product/summary.json'])['integration'] is False


def test_local_untracked_evidence_is_checked(tmp_path):
    import subprocess
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    target = tmp_path / BENCHMARKS / 'new.json'
    target.parent.mkdir()
    target.write_bytes(b'x' * (guard.FILE_BYTES + 1))
    with pytest.raises(ValueError, match='oversized'):
        guard.evaluate(guard.working_tree(str(tmp_path)), {}, {})


def test_pr_event_uses_exact_base(monkeypatch, tmp_path):
    import json
    event = tmp_path / 'event.json'
    event.write_text(json.dumps({'pull_request': {'base': {'sha': 'b' * 40}}}))
    monkeypatch.setenv('GITHUB_EVENT_PATH', str(event))
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'pull_request')
    monkeypatch.setattr(sys, 'argv', ['check_benchmark_evidence.py'])
    seen = {}
    def capture(**kwargs):
        seen.update(kwargs)
        return {'passed': True}
    monkeypatch.setattr(guard, 'check', capture)
    guard.main()
    assert seen['base'] == 'b' * 40


def test_empty_pr_base_cannot_fallback(monkeypatch, tmp_path):
    event = tmp_path / 'event.json'
    event.write_text('{"pull_request":{"base":{"sha":""}}}')
    monkeypatch.setenv('GITHUB_EVENT_PATH', str(event))
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'pull_request')
    monkeypatch.setattr(sys, 'argv', ['check_benchmark_evidence.py'])
    with pytest.raises(ValueError, match='base unavailable'):
        guard.main()


def test_public_source_cli_wires_guard_before_inventory():
    import ast
    source = (guard.ROOT / 'scripts/check_public.py').read_text()
    tree = ast.parse(source)
    block = tree.body[-1]
    assert isinstance(block, ast.If)
    calls = [node.value.func.id for node in block.body
             if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
             and isinstance(node.value.func, ast.Name)]
    assert calls[0] == 'check_evidence'
