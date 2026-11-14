"""Keep WASI write error repair bound to the pinned helper preimages."""
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[1] / 'scripts'))
from layout import FIXTURES, GENERATED_CODE
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from runtime_write import apply,CHANGES


def test_write_adapter_matches_installed_helpers():
    raw=(ROOT/(FIXTURES / 'pinned-fd-write.go.txt')).read_text()
    current=(ROOT/(GENERATED_CODE / 'base/base.go')).read_text()
    parts=[]
    for start,end in [('func writeVec(', '// fdSrcLocked'),
                      ('func (w *WasiStubs) Fd_write(', 'func (w *WasiStubs) Fd_sync('),
                      ('func (w *WasiStubs) Fd_write64(', 'func (w *WasiStubs) Proc_exit64(')]:
        begin=current.index(start);parts.append(current[begin:current.index(end,begin)])
    assert ''.join(apply('code/base/base.go',raw).split())==''.join(''.join(parts).split())
    assert apply('unrelated.go',raw)==raw


@pytest.mark.parametrize('index',range(3))
@pytest.mark.parametrize('mutation',['missing','duplicate'])
def test_write_adapter_rejects_changed_preimages(index,mutation):
    raw=(ROOT/(FIXTURES / 'pinned-fd-write.go.txt')).read_text()
    old=CHANGES[index][0]
    changed=raw.replace(old,'changed-preimage',1) if mutation=='missing' else raw+'\n'+old
    with pytest.raises(ValueError,match='preimage changed'):
        apply('code/base/base.go',changed)
