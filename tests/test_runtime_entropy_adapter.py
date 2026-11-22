"""Entropy host adaptation remains bound to its canonical input/output."""
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from runtime_entropy import apply,CHANGES


def test_entropy_adapter_matches_host_output():
    raw=(ROOT/'tests/fixtures/pinned-entropy-host.go.txt').read_text()
    output=apply('main.go',raw)
    current=(ROOT/'internal/generatedgo/main.go').read_text()
    for begin in ('func (f entropyFS) OpenFile(', 'func (f entropyFS) Stat('):
        a=output.index(begin);piece=output[a:output.index('\n}\n',a)+3]
        assert piece in current
    assert 'github.com/masahitojp/mariamem/internal/entropyfs' in current
    assert apply('other.go',raw)==raw
    with pytest.raises(ValueError,match='preimage changed'):
        apply('main.go',output)


@pytest.mark.parametrize('index',range(3))
@pytest.mark.parametrize('mutation',('missing','duplicate'))
def test_entropy_adapter_rejects_changed_preimage(index,mutation):
    raw=(ROOT/'tests/fixtures/pinned-entropy-host.go.txt').read_text();old=CHANGES[index][0]
    raw=raw.replace(old,'changed',1) if mutation=='missing' else raw+'\n'+old
    with pytest.raises(ValueError,match='preimage changed'):
        apply('main.go',raw)
