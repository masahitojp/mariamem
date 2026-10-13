"""Canonical transpilation checks remain fail-closed without obsolete images."""
import importlib.util
import json
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
spec = importlib.util.spec_from_file_location('generated_runtime_inventory', ROOT/'scripts/verify_generated_runtime.py')
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


@pytest.fixture
def canonical(tmp_path, monkeypatch):
    source = tmp_path/'internal/generatedgo'
    source.mkdir(parents=True)
    # Minimal inert inventory still stages each independently owned primitive.
    # Use the owner directory, not the installer's list, to catch omissions.
    import shutil
    owner = tmp_path/'scripts/runtime_correctness'
    shutil.copytree(ROOT/'scripts/runtime_correctness', owner)
    for template in owner.glob('*.txt'):
        target = source/'code/base'/template.name.removesuffix('.txt')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template, target)
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
    import shutil
    shutil.copytree(ROOT/'scripts/runtime_correctness', project/'scripts/runtime_correctness')
    (module/'generated/base').mkdir(parents=True)
    unit = module/'generated/base/unit.go'
    unit.write_text('package base\n')
    # The installer now binds a real single-guest allocation ABI. Keep this
    # inclusion test small while supplying checked raw function preimages;
    # do not mock/disable that input guard or reduce the ownership assertions.
    import re
    from runtime_atomic_loads import SUBWORD, CMP
    from runtime_thread_lifetime import FUNCTIONS, GUEST_SHA256, function
    (module/'generated/base/base.go').write_text(
        'package base\ntype Module struct {\n\tThreadStart func(*Module, int32, int32)\n}\n'
        + SUBWORD + '\n' + CMP + '\n'
        + 'func (w *WasiStubs) Sched_yield(m *Module) int32 {\n\truntime.Gosched()\n\treturn _wasiESUCCESS\n}\n'
        + 'const _wasiESUCCESS int32 = 0\n')
    for relative, (fn, _) in FUNCTIONS.items():
        body = function((canonical/relative).read_text(), fn)
        if fn == 'Fn153':
            body = re.sub(r'(func Fn153\(m \*base.Module, l0 int32\) \{\n)\s*if base.DeferThreadAllocationFree\(m, l0\) \{\s*return\s*\}\n', r'\1', body, count=1)
        target = module/'generated'/relative.removeprefix('code/')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('package generated\n'+body)
    data = b'fixture data'
    (module/'generated/data.bin').write_bytes(data)
    (project/'release').mkdir()
    (project/'release/generated-go-inputs.json').write_text(json.dumps({
        'candidate_files_sha256': {p.relative_to(module).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in module.rglob('*.go')},
        'data_sha256': hashlib.sha256(data).hexdigest(), 'guest_sha256': GUEST_SHA256}))
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


def test_repository_inventory_matches_committed_provenance():
    # Synthetic negative cases cannot detect an edited real generated file.
    verifier.main()


def test_generated_edit_reports_the_file_and_does_not_bless_it(canonical):
    (canonical/'internal/generatedgo/entry.go').write_text('changed')
    with pytest.raises(ValueError, match='entry.go.*canonical generator/adapter'):
        verifier.main()


def test_generated_source_cannot_be_hidden_as_handwritten(canonical, monkeypatch):
    monkeypatch.setattr(verifier, 'HANDWRITTEN_FILES', ('entry.go',))
    with pytest.raises(ValueError, match='ownership overlaps'):
        verifier.main()


def test_pinned_driver_adapter_contains_snapshot_attribution():
    import hashlib
    spec = importlib.util.spec_from_file_location('driver_installer', ROOT/'scripts/generate_runtime.py')
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    raw = (ROOT/'tests/fixtures/generated-driver.go.txt').read_bytes()
    pins = json.loads((ROOT/'release/generated-go-inputs.json').read_text())
    assert hashlib.sha256(raw).hexdigest() == pins['candidate_files_sha256']['main.go']
    adapted = installer.adapt_driver(raw.decode().replace(installer.OLD, installer.NEW))
    canonical = (ROOT/'internal/generatedgo/main.go').read_text()
    # Compare the changed export boundary before gofmt, without a Go prerequisite
    # for Python-only checks. Exact whole-driver pinned-gofmt bytes are recorded
    # in repair evidence; existing memory glue also has gofmt-normalized semicolons.
    def export_body(text):
        return text[text.index('func exportTransfer('):text.index('func verifyCompiledGuest(')]
    assert ''.join(export_body(adapted).split()) == ''.join(export_body(canonical).split())
    assert '"context"' in adapted and '"github.com/masahitojp/mariamem/internal/timing"' in adapted
    with pytest.raises(ValueError, match='driver fragment changed'):
        installer.adapt_driver(raw.decode().replace('return os.WriteFile(dst, b, 0600)', 'return nil'))

@pytest.mark.parametrize('family', ['narrow_load', 'narrow_write'])
@pytest.mark.parametrize('change', ['output', 'owner', 'missing'])
def test_template_owned_primitive_rejects_drift(canonical, change, family):
    owner = canonical/f'scripts/runtime_correctness/{family}_darwin_arm64.s.txt'
    output = canonical/f'internal/generatedgo/code/base/{family}_darwin_arm64.s'
    if change == 'output': output.write_text('changed')
    elif change == 'owner': owner.write_text('changed')
    else: owner.unlink()
    with pytest.raises(ValueError, match='template-owned'):
        verifier.main()
