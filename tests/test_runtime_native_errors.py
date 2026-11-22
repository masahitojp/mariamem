"""OS error adapters preserve the pinned WASI helper boundary."""
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from runtime_native_errors import apply, CHANGES


def fixture():
    return (ROOT/'tests/fixtures/pinned-native-errors.go.txt').read_text()


def test_native_error_adapter_reproduces_installed_helpers():
    current=(ROOT/'internal/generatedgo/code/base/base.go').read_text()
    fragments=[]
    for start in ('func mapOSError(', 'func (w *WasiStubs) Fd_allocate('):
        a=current.index(start)
        fragments.append(current[a:current.index('\n}\n',a)+3])
    assert apply('code/base/base.go',fixture()).split()==('\n'.join(fragments)).split()
    assert apply('other.go',fixture())==fixture()
    with pytest.raises(ValueError,match='preimage changed'):
        apply('code/base/base.go',apply('code/base/base.go',fixture()))


@pytest.mark.parametrize('index',range(2))
@pytest.mark.parametrize('mutation',('missing','duplicate'))
def test_native_error_adapter_rejects_unexpected_preimages(index,mutation):
    text=fixture(); old=CHANGES[index][0]
    text=text.replace(old,'changed',1) if mutation=='missing' else text+'\n'+old
    with pytest.raises(ValueError,match='preimage changed'):
        apply('code/base/base.go',text)
