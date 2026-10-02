"""Canonical cold-copy contents, sparse data and exclusive destination contracts."""
import hashlib
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_presized_cold_copy_exact_contents_and_no_overwrite(tmp_path):
    src = tmp_path / 'wasm'
    src.mkdir()
    helper = src / 'snapshot_fs.inc'
    helper.write_bytes((ROOT / 'guest/snapshot_fs.inc').read_bytes())
    harness = tmp_path / 'copy.c'
    harness.write_text('#include <stdio.h>\n#include <string.h>\n#include <sys/stat.h>\n#include <errno.h>\n#include <unistd.h>\n#include "wasm/snapshot_fs.inc"\nint main(int argc,char**argv){return argc!=3||snapshot_copy(argv[1],argv[2],0);}\n')
    binary = tmp_path / 'copy'
    subprocess.run(['cc', '-O2', '-Wall', '-Werror', str(harness), '-o', str(binary)], check=True)
    original = tmp_path / 'original'
    original.mkdir()
    (original / 'nested').mkdir()
    (original / 'empty').touch()
    (original / 'nested/blocks').write_bytes(bytes(range(256)) * 1025)
    with (original / 'sparse').open('wb') as f:
        f.write(b'first')
        f.seek(2 * 1024 * 1024)
        f.write(b'last')
    destination = tmp_path / 'destination'
    subprocess.run([str(binary), str(original), str(destination)], check=True)
    for p in original.rglob('*'):
        if p.is_file():
            q = destination / p.relative_to(original)
            assert p.stat().st_size == q.stat().st_size
            assert hashlib.sha256(p.read_bytes()).digest() == hashlib.sha256(q.read_bytes()).digest()
    assert subprocess.run([str(binary), str(original), str(destination)]).returncode != 0
    # Renamed source directories and reused names do not change the copy's semantics.
    moved = tmp_path / 'moved'
    original.rename(moved)
    original.mkdir()
    (original / 'different').write_bytes(b'unrelated')
    subprocess.run([str(binary), str(moved), str(tmp_path / 'second')], check=True)
    assert (tmp_path / 'second/nested/blocks').read_bytes() == (moved / 'nested/blocks').read_bytes()

