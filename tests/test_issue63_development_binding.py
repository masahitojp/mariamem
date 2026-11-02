"""The experiment must not accept another guest or a changed worker ABI."""
import importlib.util
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('issue63_binding', ROOT/'tests/issue63_install_dev.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


def source(tmp_path):
    for name, (fn, _) in adapter.binding.FUNCTIONS.items():
        text = (ROOT/'internal/generatedgo'/name).read_text()
        if fn == 'Fn153':
            text = re.sub(r'(func Fn153\(m \*base.Module, l0 int32\) \{\n)\s*if base.DeferThreadAllocationFree\(m, l0\) \{\s*return\s*\}\n', r'\1', text, count=1)
        path = tmp_path/'generated'/name.removeprefix('code/')
        path.parent.mkdir(parents=True)
        path.write_text(adapter.binding.function(text, fn))
    return tmp_path


def test_exact_guest_and_unchanged_bodies(tmp_path):
    assert len(adapter.authorize(adapter.GUEST, source(tmp_path))) == 3


def test_other_guest_and_canonical_policy_stay_rejected(tmp_path):
    with pytest.raises(ValueError, match='exact Issue63'):
        adapter.authorize('0'*64, source(tmp_path))
    files = {'generated/base/base.go', *('generated/'+p.removeprefix('code/') for p in adapter.binding.FUNCTIONS)}
    with pytest.raises(ValueError, match='unreviewed'):
        adapter.binding.validate_inputs(adapter.GUEST, files)


@pytest.mark.parametrize('name', list(adapter.binding.FUNCTIONS))
def test_each_changed_body_is_rejected(tmp_path, name):
    root = source(tmp_path)
    p = root/'generated'/name.removeprefix('code/')
    text = p.read_text()
    changed = text.replace('mBase := m.M', 'mBase := unsafe.Pointer(nil)', 1)
    assert text != changed
    p.write_text(changed)
    with pytest.raises(ValueError, match='worker ABI changed'):
        adapter.authorize(adapter.GUEST, root)
