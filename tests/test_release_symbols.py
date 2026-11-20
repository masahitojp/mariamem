"""Real Go binaries expose trimpath's omitted link flags without a product rebuild."""
import os
from pathlib import Path
import subprocess
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from release_symbols import require_stripped

@pytest.mark.parametrize('target', ['darwin', 'linux'])
def test_actual_go_strip_with_trimpath(tmp_path, target):
    source=tmp_path/'main.go';source.write_text('package main\nfunc main(){}\n')
    env=dict(os.environ,GOTOOLCHAIN='go1.26.11',CGO_ENABLED='0',GOOS=target,GOARCH='arm64')
    for flags in [[], ['-ldflags=-s -w'], ['-ldflags=-w']]:
        binary=tmp_path/'host'
        subprocess.run(['go','build','-trimpath',*flags,'-o',str(binary),str(source)],env=env,check=True,capture_output=True)
        if flags==['-ldflags=-s -w']:
            require_stripped(binary)
        else:
            with pytest.raises(ValueError,match='omit symbols'):
                require_stripped(binary)

def test_unknown_and_truncated_rejected(tmp_path):
    host=tmp_path/'host'
    for value in [b'bad',b'\x7fELF\x02\x01']:
        host.write_bytes(value)
        with pytest.raises(ValueError):require_stripped(host)
