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
 if(argc>4) return restore_equal(argv[1],argv[2],0) ? 1 : 0;
 if(argc>3) {
   rp_cost cost={0};
   rp_stamp begin={100,200,300,7},end={101,201,299,7};
   if(!strcmp(argv[3],"failed")) { end.valid=5; end.thread=301; }
   rp_add(&cost,begin,end,12); rp_write_cost(stdout,&cost); return 0;
 }
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
    for mode, failed, regressed in [('regressed', 0, 4), ('failed', 2, 0)]:
        result = subprocess.run([str(binary), str(src), str(dest), mode], capture_output=True, text=True, check=True)
        cost = json.loads(result.stdout)
        assert cost['invalid_clock'] is True
        assert cost['clock_error']['failed_mask'] == failed
        assert cost['clock_error']['regressed_mask'] == regressed
        assert cost['clock_error']['first_begin'] == [100, 200, 300]
        assert cost['wall_ns'] == cost['process_cpu_ns'] == cost['thread_cpu_ns'] == 0
        assert cost['bytes'] == 12
    equal_command = [str(binary), str(src), str(dest), 'compare', 'exact']
    assert subprocess.run(equal_command, capture_output=True).returncode == 0
    (dest/'extra').write_bytes(b'')
    assert subprocess.run(equal_command, capture_output=True).returncode == 1
    (dest/'extra').unlink()
    (dest/'large').write_bytes(b'y'*150000)
    assert subprocess.run(equal_command, capture_output=True).returncode == 1
    (dest/'large').write_bytes((src/'large').read_bytes())
    (dest/'empty').unlink()
    assert subprocess.run(equal_command, capture_output=True).returncode == 1
    (dest/'empty').write_bytes(b'')
    # Existing exclusive-create and symlink rejection remain intact.
    assert subprocess.run([str(binary), str(src), str(dest)], capture_output=True).returncode == 1
    (src/'link').symlink_to(src/'large')
    assert subprocess.run([str(binary), str(src), str(tmp_path/'linked')], capture_output=True).returncode == 1
    probe['stages']['read']['invalid_clock'] = True
    probe['stages']['read']['clock_error'] = {'regressed_mask': 4}
    with pytest.raises(ValueError, match='read.*regressed_mask.*4'):
        validate(probe)
    probe['stages']['read']['invalid_clock'] = False
    probe['stages']['read']['bytes'] -= 1
    with pytest.raises(ValueError, match='byte count'):
        validate(probe)


def test_source_probe_wrapper_and_separate_staging(tmp_path):
    cc=shutil.which('cc')
    if not cc:pytest.skip('C compiler unavailable')
    # Redirect only hard-coded guest paths for this native correctness fixture.
    overlay=(ROOT/'guest/snapshot_fs.inc').read_text()
    for path,name in [('/snapshot-in/data','test_source'),('/restore-source','test_staging'),('/mariadb','test_dest')]:
        overlay=overlay.replace('"'+path+'"',name)
    (tmp_path/'copy.inc').write_text(overlay)
    (tmp_path/'check.c').write_text('''#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <sys/stat.h>
#include <unistd.h>
#define MARIAMEM_DIAGNOSTIC_TEST
#include "init_diagnostics.inc"
static const char *test_source,*test_staging,*test_dest;
#include "copy.inc"
int main(int argc,char **argv) {
 test_source=argv[1];test_staging=argv[2];test_dest=argv[3];
 setenv("MARIAMEM_RESTORE_DIAGNOSTICS","1",1);
 setenv("MARIAMEM_SOURCE_BOUNDARY_PROBE","1",1);
 if(argc>4)setenv("MARIAMEM_GUEST_RESTORE_SOURCE","1",1);
 if(snapshot_restore())return 1;
 fputs("{\\"ok\\":true",stdout);restore_probe_write(stdout);fputs("}",stdout);return 0;
}
''')
    binary=tmp_path/'probe'
    subprocess.run([cc,'-std=c11','-D_POSIX_C_SOURCE=200809L','-I',str(ROOT/'guest'),str(tmp_path/'check.c'),'-o',str(binary)],check=True)
    original=tmp_path/'original';original.mkdir();(original/'file').write_bytes(b'z'*150000)
    for condition in ('host','guest'):
        dest=tmp_path/(condition+'-dest');stage=tmp_path/(condition+'-stage')
        cmd=[str(binary),str(original),str(stage),str(dest)]
        if condition=='guest':cmd+=['guest']
        raw=json.loads(subprocess.check_output(cmd,text=True))
        assert raw['restore_identity_verified'] is True and raw['restore_source']==condition
        assert raw['restore_copy']['stages']['read']['bytes']==150000
        assert raw['restore_verification']['calls']==(2 if condition=='guest' else 1)
        assert (dest/'file').read_bytes()==(original/'file').read_bytes()
        if condition=='guest':
            assert raw['restore_prestage']['stages']['read']['bytes']==150000
            assert (stage/'file').read_bytes()==(original/'file').read_bytes()
        else:assert 'restore_prestage' not in raw
