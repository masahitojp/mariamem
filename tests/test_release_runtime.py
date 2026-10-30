"""Sharing artifacts must retain the real wheel verifier and reject substitutions."""
from pathlib import Path
import sys

import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import release_runtime as runtime
from generated_release import read, write
from test_generated_release import host_wheel


@pytest.fixture
def shared(host_wheel, monkeypatch):
    root, wheel, manifest, make = host_wheel
    root = root.resolve()
    record = root/'tests/evidence/alpha-wheel.json'
    data = read(record)
    data['host_buildinfo'] = 'original-host: go1.26.10\n'+data['host_buildinfo']
    write(record, data)
    monkeypatch.setattr(runtime, 'require_commit', lambda *args: None)
    monkeypatch.setattr(runtime, 'current_target', lambda root: {'platform': 'darwin-arm64'})
    monkeypatch.setattr(runtime, 'verify_go_binary', lambda *args: data['host_buildinfo'])
    return root, wheel, record


def test_stage_uses_exact_wheel_bytes_and_is_idempotent(shared):
    root, wheel, _ = shared
    selected, host = runtime.stage(root, 'a'*40)
    assert selected == wheel and host.read_bytes() == b'host'
    assert host.stat().st_mode & 0o111 == 0o111
    assert runtime.stage(root, 'a'*40) == (selected, host)


@pytest.mark.parametrize('failure', ['source', 'wheel-bytes', 'host-bytes', 'extra-wheel', 'path', 'platform', 'binary-source', 'buildinfo', 'symlink'])
def test_shared_runtime_rejects_wrong_or_ambiguous_inputs(shared, monkeypatch, failure):
    root, wheel, record = shared
    if failure == 'wheel-bytes': wheel.write_bytes(wheel.read_bytes()+b'corruption')
    elif failure == 'host-bytes': (root/'build/mariamem-host').write_bytes(b'other-host')
    elif failure == 'extra-wheel': (wheel.parent/'other.whl').write_bytes(b'extra')
    elif failure == 'path':
        data = read(record); data['wheel'] = '../'+wheel.name; write(record, data)
    elif failure == 'platform':
        monkeypatch.setattr(runtime, 'current_target', lambda root: {'platform': 'ubuntu24.04-x86_64'})
    elif failure == 'binary-source':
        def reject(*args): raise ValueError('binary source differs')
        monkeypatch.setattr(runtime, 'verify_go_binary', reject)
    elif failure == 'buildinfo': monkeypatch.setattr(runtime, 'verify_go_binary', lambda *args: 'host\nother flags')
    elif failure == 'symlink': (root/'build/mariamem-host').symlink_to(wheel)
    with pytest.raises(ValueError):
        runtime.stage(root, ('b' if failure == 'source' else 'a')*40)


def test_release_builds_one_wheel_and_every_feature_uses_it():
    text = (ROOT/'.github/workflows/release-candidate-ready.yml').read_text()
    assert text.count('python scripts/build_alpha.py --ci-candidate') == 1
    assert 'needs: [resolve, guest, runtime]' in text
    assert "if: needs.resolve.outputs.mode != 'full'" in text
    assert '--mode acceptance-only --candidate-run' in text
    candidate = text.split('  candidate:\n', 1)[1].split('  verification:\n', 1)[0]
    assert 'build_alpha.py' not in candidate
    assert 'release-runtime-${{ matrix.runner }}-${{ needs.resolve.outputs.source_sha }}' in candidate
    assert 'verify.py check\n' in candidate and 'verify.py integration --host build/mariamem-host' in candidate
    for name in ['live-host', 'dump-import-productization', 'django-lifecycle', 'connection-routing', 'preparation-migration', 'worker-failure']:
        called = (ROOT/'.github/workflows'/f'{name}.yml').read_text()
        assert 'release-runtime-${{ matrix.os }}-${{ inputs.source_commit }}' in called
        assert 'python scripts/release_runtime.py --source-commit "$SOURCE_COMMIT"' in called
        assert 'scripts/build_alpha.py --ci-candidate' not in called
        assert 'go build -p 1 -trimpath -o build/mariamem-host ' not in called
    installed = (ROOT/'tests/live_acceptance/installed.py').read_text()
    assert 'build_alpha.py' not in installed and 'stage(ROOT, args.expected_source_commit)' in installed


def test_candidate_cache_retains_race_compilation_but_never_skips_tests():
    text = (ROOT/'.github/workflows/release-candidate-ready.yml').read_text()
    candidate = text.split('  candidate:\n', 1)[1].split('  verification:\n', 1)[0]
    restore = candidate.index('uses: actions/cache/restore@')
    discard = candidate.index('run: go clean -testcache')
    checks = candidate.index('python scripts/verify.py check')
    integration = candidate.index('python scripts/verify.py integration --host')
    save = candidate.index('uses: actions/cache/save@')
    assert restore < discard < checks < integration < save
    key = next(line for line in candidate.splitlines() if 'key: release-core-race-' in line)
    for boundary in ('runner.os', 'runner.arch', 'go1.26.10', "hashFiles('go.mod', 'go.sum')", 'needs.resolve.outputs.source_sha'):
        assert boundary in key
    assert 'restore-keys:' in candidate  # Later source revisions may reuse compilation.
    assert candidate.count('${{ steps.compiler-paths.outputs.build }}') == 2
    assert candidate.count('${{ steps.compiler-paths.outputs.modules }}') == 2
    assert 'key: ${{ steps.compiler-cache.outputs.cache-primary-key }}' in candidate
    assert "if: success() && needs.resolve.outputs.runtime_reused != 'true' && steps.compiler-cache.outputs.cache-hit != 'true'" in candidate
    # Cache outages/misses are optimization failures, never qualification bypasses.
    assert candidate.count('continue-on-error: true') == 2
    qualify = candidate.split('      - name: Qualify and freeze', 1)[1].split('      - name: Save compiler', 1)[0]
    assert 'cache-hit' not in qualify and 'continue-on-error' not in qualify
    assert "if [ '${{ needs.resolve.outputs.runtime_reused }}' = true ]; then" in qualify
    assert 'go1.26.10 python scripts/verify.py integration' in qualify
    assert '-count=1' in (ROOT/'scripts/verify.py').read_text().split('def integration(', 1)[1]
