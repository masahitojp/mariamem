"""Canonical transpilation checks remain fail-closed without obsolete images."""
import importlib.util
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('generated_runtime_inventory', ROOT/'scripts/verify_generated_runtime.py')
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


@pytest.fixture
def canonical(tmp_path, monkeypatch):
    source = tmp_path/'internal/generatedgo'
    source.mkdir(parents=True)
    pins = tmp_path/'release/generated-go-inputs.json'
    pins.parent.mkdir()
    pins.write_text(json.dumps({'guest_sha256': 'a'*64}))
    generated = source/'entry.go'
    generated.write_text('package generatedgo\n')
    record = {'input_manifest_sha256': verifier.digest(pins), 'guest_sha256': 'a'*64,
              'files_sha256': {'entry.go': verifier.digest(generated)}}
    (source/'provenance.json').write_text(json.dumps(record))
    monkeypatch.setattr(verifier, 'ROOT', tmp_path)
    return tmp_path


def test_canonical_inventory_needs_no_executable_image(canonical):
    assert not (canonical/'internal/builtinruntime').exists()
    verifier.main()


@pytest.mark.parametrize('change', ['modified', 'extra', 'missing', 'pins', 'guest'])
def test_canonical_identity_changes_are_rejected(canonical, change):
    source = canonical/'internal/generatedgo'
    if change == 'modified':
        (source/'entry.go').write_text('modified')
    elif change == 'extra':
        (source/'extra.go').write_text('extra')
    elif change == 'missing':
        (source/'entry.go').unlink()
    elif change == 'pins':
        (canonical/'release/generated-go-inputs.json').write_text('{}')
    else:
        path = source/'provenance.json'
        record = json.loads(path.read_text())
        record['guest_sha256'] = 'b'*64
        path.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        verifier.main()
