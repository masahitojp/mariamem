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
    from workflow_model import load, steps, action
    model = load(ROOT / '.github/workflows/release-candidate-ready.yml')
    assert {step['with']['go-version'] for step in steps(model) if action(step, 'actions/setup-go')} == {version}
    pins = {owner['env']['GOTOOLCHAIN'] for owner in [model, *model['jobs'].values(), *steps(model)] if 'GOTOOLCHAIN' in owner.get('env', {})}
    assert pins == {'go' + version}
