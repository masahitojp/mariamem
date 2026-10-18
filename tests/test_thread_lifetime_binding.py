"""Fail-closed guest ABI/reclaimer installation, independent of runtime scheduling tests."""
import importlib.util
from pathlib import Path
import re
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('thread_binding', ROOT/'scripts/runtime_thread_lifetime.py')
binding = importlib.util.module_from_spec(spec)
spec.loader.exec_module(binding)


def preimage(name):
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


def test_prepared_spike_identity_is_explicit_and_not_a_wildcard():
    files = {'generated/base/base.go', *('generated/'+p.removeprefix('code/') for p in binding.FUNCTIONS)}
    binding.validate_inputs(binding.PREPARED_SPIKE_GUEST, files)
    with pytest.raises(ValueError, match='unreviewed'):
        binding.apply('code/base/base.go', preimage('code/base/base.go'), guest_sha256='f'*64)
    for name in binding.FUNCTIONS:
        if binding.FUNCTIONS[name] != binding.PREPARED_SPIKE_FUNCTIONS[name]:
            with pytest.raises(ValueError, match='function changed'):
                binding.apply(name, preimage(name), guest_sha256=binding.PREPARED_SPIKE_GUEST)


@pytest.mark.parametrize('guest_sha256', [binding.MULTI_SPIKE_GUEST, binding.OPTION_SPIKE_GUEST])
@pytest.mark.parametrize('name', list(binding.PREPARED_SPIKE_FUNCTIONS))
def test_multi_spike_keeps_exact_body_mutation_gate(name, guest_sha256):
    fn = binding.PREPARED_SPIKE_FUNCTIONS[name][0]
    text = (ROOT/'docs/reviews/v06x-prepared-spike-evidence'/('selected-'+fn+'-new.go.txt')).read_text()
    binding.apply(name, text, guest_sha256=guest_sha256)
    assert 'mBase := m.M' in text
    changed = text.replace('mBase := m.M', 'mBase := unsafe.Pointer(nil)', 1)
    with pytest.raises(ValueError, match='function changed'):
        binding.apply(name, changed, guest_sha256=guest_sha256)
