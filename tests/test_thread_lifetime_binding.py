"""Fail-closed guest ABI/reclaimer installation, independent of runtime scheduling tests."""
import importlib.util
import json
from pathlib import Path
import re
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('thread_binding', ROOT/'scripts/runtime_thread_lifetime.py')
binding = importlib.util.module_from_spec(spec)
spec.loader.exec_module(binding)


def preimage(name):
    # During staged implementation canonical generated files still belong to
    # the old guest. New candidate preimages are exact, reviewed converter output,
    # never normalized into acceptance. Native development CI also checks these
    # against the freshly generated candidate before executing it.
    provenance=json.loads((ROOT/'internal/generatedgo/provenance.json').read_text())
    if provenance['guest_sha256'] != binding.GUEST_SHA256 and name in binding.FUNCTIONS:
        identity=json.loads((ROOT/'tests/fixtures/prepared-p2-binding/identity.json').read_text())
        assert provenance['guest_sha256']==identity['baseline_guest_sha256'],'unexpected canonical guest during prepared transition'
        assert binding.GUEST_SHA256==identity['guest_sha256']
        fn=binding.FUNCTIONS[name][0]
        return (ROOT/'tests/fixtures/prepared-p2-binding'/(fn+'.txt')).read_text()
    text = (ROOT/'internal/generatedgo'/name).read_text()
    # Construct raw input from canonical output only for mutation tests. The
    # independent regeneration command is the valid-input acceptance oracle.
    if name == 'code/base/base.go':
        text = re.sub(r'(?m)^\s*ThreadLifetime\s+\*ThreadLifetime\n', '', text)
    elif name == 'code/p3/p3_pure.go':
        text = re.sub(r'(func Fn153\(m \*base.Module, l0 int32\) \{\n)\s*if base.DeferThreadAllocationFree\(m, l0\) \{\s*return\s*\}\n', r'\1', text, count=1)
    return text


@pytest.mark.parametrize('name', list(binding.FUNCTIONS))
def test_bound_function_change_is_rejected(name):
    text = preimage(name)
    binding.apply(name, text)
    fn = binding.FUNCTIONS[name][0]
    body = binding.function(text, fn)
    changed = text.replace(body, body.replace('mBase := m.M', 'mBase := unsafe.Pointer(nil)', 1), 1)
    with pytest.raises(ValueError, match='function changed'):
        binding.apply(name, changed)


@pytest.mark.parametrize('name,address', [
    ('code/p3/p3_pure.go', '15246156'),
    ('code/p5/p5_pure.go', '15244737'),
])
@pytest.mark.parametrize('earlier_same_literal', [False, True])
def test_another_address_relocation_is_not_accepted(name, address, earlier_same_literal):
    # The offline review compared one observed relocation. Runtime matching
    # still requires the exact complete preimage, including every address.
    text=preimage(name)
    if earlier_same_literal:
        # Installed part files contain other functions with the same address.
        # A file-wide first replacement can mutate an unrelated function.
        text='func Fn0(m *base.Module) { _ = '+address+' }\n\n'+text
    fn=binding.FUNCTIONS[name][0]
    body=binding.function(text,fn)
    assert address in body
    changed_body=body.replace(address,str(int(address)+4),1)
    assert changed_body != body
    changed=text.replace(body,changed_body,1)
    assert binding.function(changed,fn)==changed_body
    with pytest.raises(ValueError,match='function changed'):
        binding.apply(name,changed)


def test_duplicate_module_hook_is_rejected():
    text = binding.apply('code/base/base.go', preimage('code/base/base.go'))
    with pytest.raises(ValueError, match='Module shape changed'):
        binding.apply('code/base/base.go', text)


def test_late_yield_contract_change_is_rejected():
    text = preimage('code/base/base.go').replace('return _wasiESUCCESS\n}\n\n// Poll_oneoff', 'return _wasiEIO\n}\n\n// Poll_oneoff', 1)
    with pytest.raises(ValueError, match='memory-free host yield'):
        binding.apply('code/base/base.go', text)


def test_guest_and_required_file_identity():
    files = {'generated/base/base.go', *('generated/'+p.removeprefix('code/') for p in binding.FUNCTIONS)}
    binding.validate_inputs(binding.GUEST_SHA256, files)
    with pytest.raises(ValueError, match='unreviewed'):
        binding.validate_inputs('0'*64, files)
    for file in files:
        with pytest.raises(ValueError, match='unreviewed'):
            binding.validate_inputs(binding.GUEST_SHA256, files-{file})


@pytest.mark.parametrize('old_identity', ['baseline_guest_sha256', 'previous_guest_sha256', 'p1_guest_sha256', 'initial_p2_guest_sha256'])
def test_old_guest_is_not_an_alternate_allowed_identity(old_identity):
    old=json.loads((ROOT/'tests/fixtures/prepared-p2-binding/identity.json').read_text())[old_identity]
    files={'generated/base/base.go',*('generated/'+p.removeprefix('code/') for p in binding.FUNCTIONS)}
    with pytest.raises(ValueError,match='unreviewed'):
        binding.validate_inputs(old,files)


@pytest.mark.parametrize('mutate_offset',[False,True])
def test_memory_initialization_binding(tmp_path,mutate_offset):
    import check_prepared_p1_binding as checker
    identity=json.loads((ROOT/'tests/fixtures/prepared-p2-binding/identity.json').read_text())
    body=(ROOT/'tests/fixtures/prepared-p2-binding/memory-init.txt').read_text()
    target=tmp_path/identity['memory_init']['file'];target.parent.mkdir(parents=True)
    target.write_text(body.replace('int32(8388608)','int32(8388612)',1) if mutate_offset else body)
    if mutate_offset:
        with pytest.raises(AssertionError,match='memory initialization changed'):
            checker.check_memory_initialization(tmp_path,identity)
    else:checker.check_memory_initialization(tmp_path,identity)
