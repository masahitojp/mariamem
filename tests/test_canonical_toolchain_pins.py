"""Canonical generation must not silently switch back to an older Go compiler."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_canonical_generation_matches_authoritative_go_pin():
    version = json.loads((ROOT / 'release/generated-go-toolchain.json').read_text())['go']
    assert json.loads((ROOT / 'release/inputs.lock.json').read_text())['toolchain']['go'] == version
    for name in ('scripts/regenerate_release_guest.py', 'scripts/generate_runtime.py',
                 'benchmarks/spikes/generated-go-integration/translate_guest.py',
                 'benchmarks/spikes/generated-go-integration/setup_candidate.py',
                 'benchmarks/spikes/generated-go-integration/readiness_replay.py',
                 'benchmarks/spikes/memory-candidate/check_fixture.py'):
        actual = set(re.findall(r'\bgo1\.\d+\.\d+\b', (ROOT / name).read_text()))
        assert actual == {'go' + version}, (name, actual, version)


def test_release_ci_uses_authoritative_go_pin():
    version = json.loads((ROOT / 'release/generated-go-toolchain.json').read_text())['go']
    text = (ROOT / '.github/workflows/release-candidate-ready.yml').read_text()
    assert set(re.findall(r'go-version:\s*[\'\"]?(\d+\.\d+\.\d+)', text)) == {version}
    assert set(re.findall(r'GOTOOLCHAIN:\s*(go1\.\d+\.\d+)', text)) == {'go' + version}
