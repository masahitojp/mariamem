"""Lane-B only: actual cold-copy helper and safe experimental-overlay order."""
import hashlib
from pathlib import Path
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_patch_runs_after_overlay_before_instrumentation():
    source = (ROOT / 'scripts/prepare_guest.py').read_text()
    assert source.index('shutil.copy2(ROOT / "guest" / name') < source.index('"patch", "-p1", "-i", str(experimental)') < source.index('diagnostic_files = instrument(source)')


def test_presized_cold_copy_exact_contents_and_no_overwrite(tmp_path):
    src = tmp_path / 'wasm'
    src.mkdir()
    helper = src / 'snapshot_fs.inc'
    helper.write_bytes((ROOT / 'guest/snapshot_fs.inc').read_bytes())
    subprocess.run(['patch', '-p1', '-i', str(ROOT / 'guest/experimental.patch')], cwd=tmp_path, check=True, capture_output=True)
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


def test_installer_replaces_nested_generated_functions_and_removes_old_code(tmp_path):
    import runpy
    install = runpy.run_path(str(ROOT / 'benchmarks/snapshotpreallocation/install_experiment.py'))['install_function_tree']
    source, destination = tmp_path / 'raw', tmp_path / 'code'
    (source / 'p0').mkdir(parents=True)
    (source / 'base').mkdir()
    (destination / 'p0').mkdir(parents=True)
    (destination / 'obsolete').mkdir()
    (destination / 'base').mkdir()
    (source / 'generated.go').write_text('package generated\n\t_ "embed"\n//go:embed data.bin\nvar wasm2goData_data_bin []byte\n')
    (source / 'p0/function.go').write_text('package p0\nimport "example.com/mariamem-spike/generated/base"\n// new body\n')
    (source / 'base/base.go').write_text('raw base must not replace canonical adapter')
    (destination / 'p0/function.go').write_text('stale body')
    (destination / 'obsolete/stale.go').write_text('obsolete code')
    (destination / 'base/base.go').write_text('canonical adapter')
    files = install(source, destination, b'\x01\x02')
    assert len(files) == 2
    assert (destination / 'p0/function.go').read_text() == 'package p0\nimport "github.com/masahitojp/mariamem/internal/generatedgo/code/base"\n// new body\n'
    assert (destination / 'base/base.go').read_text() == 'canonical adapter'
    assert not (destination / 'obsolete').exists()
    assert '\\x01\\x02' in (destination / 'generated.go').read_text()
