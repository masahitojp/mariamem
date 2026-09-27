"""Native copy semantics and bounded structured restore measurements."""
import json
import shutil
import subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_restore_copy_diagnostics(tmp_path):
    cc = shutil.which('cc')
    if not cc:
        pytest.skip('C compiler unavailable')
    source = tmp_path/'check.c'
    source.write_text('''#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <sys/stat.h>
#include <unistd.h>
#define MARIAMEM_DIAGNOSTIC_TEST
#include "init_diagnostics.inc"
#include "snapshot_fs.inc"
int main(int argc,char **argv) {
 restore_probe.enabled=1; restore_probe.begin=rp_now();
 int rc=snapshot_copy(argv[1],argv[2],1);
 restore_probe.end=rp_now();
 fputs("{",stdout); restore_probe_write(stdout); fputs("}",stdout);
 return rc ? 1 : 0;
}
''')
    binary = tmp_path/'check'
    subprocess.run([cc, '-std=c11', '-D_POSIX_C_SOURCE=200809L', '-I', str(ROOT/'guest'), str(source), '-o', str(binary)], check=True)
    src = tmp_path/'source'; src.mkdir()
    (src/'large').write_bytes(b'x'*150000)
    (src/'empty').write_bytes(b'')
    dest = tmp_path/'dest'
    result = subprocess.run([str(binary), str(src), str(dest)], capture_output=True, text=True, check=True)
    # Writer appends a member to the existing startup document.
    probe = json.loads(result.stdout.replace('{,', '{'))['restore_copy']
    import sys
    sys.path.insert(0, str(ROOT/'benchmarks'))
    from restore_report import validate
    validate(probe)
    assert probe['file_count'] == 2 and probe['directories'] == 1
    assert probe['stages']['read']['bytes'] == 150000
    assert probe['stages']['write']['calls'] == 3
    assert (dest/'large').read_bytes() == (src/'large').read_bytes()
    # Existing exclusive-create and symlink rejection remain intact.
    assert subprocess.run([str(binary), str(src), str(dest)], capture_output=True).returncode == 1
    (src/'link').symlink_to(src/'large')
    assert subprocess.run([str(binary), str(src), str(tmp_path/'linked')], capture_output=True).returncode == 1
    probe['stages']['read']['bytes'] -= 1
    with pytest.raises(ValueError, match='byte count'):
        validate(probe)
