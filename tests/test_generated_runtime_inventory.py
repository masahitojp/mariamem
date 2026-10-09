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


def test_clean_installer_preserves_every_handwritten_file(tmp_path, monkeypatch):
    """Exercise the real install/copy path without translating or building Go.

    Derive expected glue from committed provenance, not the installer's own list:
    omitting new ownership files from that list must fail this test.
    """
    import hashlib
    import sys
    spec = importlib.util.spec_from_file_location('runtime_installer', ROOT/'scripts/generate_runtime.py')
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    canonical = ROOT/'internal/generatedgo'
    record = json.loads((canonical/'provenance.json').read_text())
    handwritten = {p.relative_to(canonical).as_posix() for p in canonical.rglob('*')
                   if p.is_file() and p.name != 'provenance.json'} - set(record['files_sha256'])
    assert {'code/base/owned_prepared.go', 'code/base/owned_prepared_test.go'} <= handwritten
    project, module, output = tmp_path/'project', tmp_path/'input', tmp_path/'output'
    for name in handwritten:
        target = project/'internal/generatedgo'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((canonical/name).read_bytes())
    (module/'generated/base').mkdir(parents=True)
    unit = module/'generated/base/unit.go'
    unit.write_text('package base\n')
    data = b'fixture data'
    (module/'generated/data.bin').write_bytes(data)
    (project/'release').mkdir()
    (project/'release/generated-go-inputs.json').write_text(json.dumps({
        'candidate_files_sha256': {'generated/base/unit.go': hashlib.sha256(unit.read_bytes()).hexdigest()},
        'data_sha256': hashlib.sha256(data).hexdigest(), 'guest_sha256': 'a'*64}))
    monkeypatch.setattr(installer, 'ROOT', project)
    monkeypatch.setattr(sys, 'argv', ['generate_runtime.py', '--source-module', str(module), '--output', str(output)])
    monkeypatch.setattr(installer.subprocess, 'check_output', lambda *a, **k: str(tmp_path/'go')+'\n')
    commands = []
    monkeypatch.setattr(installer.subprocess, 'run', lambda args, **kwargs: commands.append(args))
    installer.main()
    assert len(commands) == 1 and commands[0][1] == '-w'  # gofmt only, never a build
    installed = json.loads((output/'provenance.json').read_text())['files_sha256']
    assert not handwritten & set(installed)  # remains handwritten, not translated provenance
    actual = {p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()}
    assert actual == handwritten | set(installed) | {'provenance.json'}
    for name in handwritten:
        assert (output/name).read_bytes() == (canonical/name).read_bytes()
