"""Diagnostic collectors and source hooks: no real guest required."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
sys.path.insert(0, str(ROOT/'benchmarks'))
from guest_init_hooks import HOOKS, instrument
from init_report import summarize, validate


def test_hooks_fail_closed_and_insert_once(tmp_path):
    for name, hooks in HOOKS.items():
        path = tmp_path/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('\n'.join(anchor for anchor, _, _ in hooks))
    instrument(tmp_path)
    for name, hooks in HOOKS.items():
        text = (tmp_path/name).read_text()
        assert text.count('mariamem_init_mark(') == len(hooks)
    with pytest.raises(ValueError, match='anchor changed'):
        instrument(tmp_path)


def test_native_collector_preserves_calls_and_errno(tmp_path):
    cc = shutil.which('cc')
    if not cc:
        pytest.skip('native C compiler unavailable')
    source = tmp_path/'check.c'
    source.write_text('''#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <time.h>
#include "init_diagnostics.inc"
static void *worker(void *arg) { return arg; }
int main(int argc, char **argv) {
 init_enable();
 mariamem_init_mark("begin");
 errno=EDOM;
 void *p=__wrap_malloc(64);
 if (!p || errno!=EDOM) return 1;
 p=__wrap_realloc(p,128); if (!p) return 2;
 __wrap_free(p);
 int fd=__wrap_open(argv[1],O_CREAT|O_RDWR|O_TRUNC,0600);
 if(fd<0) return 3;
 init_opened(fd,"/mariadb/data/diagnostic.ibd",O_TRUNC);
 if(__wrap_pwrite(fd,"1234",4,0)!=4) return 4;
 char buf[4]; if(__wrap_pread(fd,buf,4,0)!=4 || memcmp(buf,"1234",4)) return 5;
 if(__wrap_ftruncate(fd,4)) return 6;
 if(__wrap_close(fd)) return 7;
 errno=E2BIG;
 if(__wrap_read(-1,buf,4)!=-1 || errno!=EBADF) return 8;
 pthread_t thread; if(__wrap_pthread_create(&thread,NULL,worker,NULL)) return 9;
 if(pthread_join(thread,NULL)) return 10;
 mariamem_init_mark("end");
 FILE *out=fopen(argv[2],"w"); if(!out) return 11;
 fputs("{\\"test\\":true",out); init_write(out); fputs("}",out); fclose(out);
 return 0;
}
''')
    executable = tmp_path/'check'
    subprocess.run([cc, '-std=c11', '-D_POSIX_C_SOURCE=200809L', '-DMARIAMEM_DIAGNOSTIC_TEST',
                    '-I', str(ROOT/'guest'), str(source), '-pthread', '-o', str(executable)], check=True)
    output = tmp_path/'record.json'
    subprocess.run([str(executable), str(tmp_path/'data'), str(output)], check=True,
                   env={'PATH': str(Path(cc).parent)})
    assert json.loads(output.read_text()) == {'test': True}
    subprocess.run([str(executable), str(tmp_path/'data'), str(output)], check=True,
                   env={'PATH': str(Path(cc).parent), 'MARIAMEM_INIT_DIAGNOSTICS': '1'})
    record = json.loads(output.read_text())['initialization']
    assert record['dropped_records'] == 0
    start, end = record['events']
    assert end['offset_ns'] >= start['offset_ns']
    assert end['pthread_creates'] == 1
    assert end['wrapped_alloc_balance_bytes'] == 0
    assert end['wrapped_alloc_requested_bytes'] == 192
    file, = record['files']
    assert file['read_bytes'] == file['write_bytes'] == 4
    assert file['truncates'] == 2
    assert file['read_calls'] == file['write_calls'] == 1


def test_report_keeps_cpu_distinct_and_rejects_missing_stages():
    # Respect source execution order, rather than sorting marker names.
    order = ['guest_main', 'restore_complete', 'embedded_begin', 'embedded_options_complete',
             'components_begin', 'plugins_begin', 'innodb_plugin_begin', 'innodb_parameters_complete',
             'innodb_runtime_begin', 'buffer_pool_begin', 'buffer_pool_complete',
             'innodb_memory_background_complete', 'innodb_open_recovery_complete',
             'innodb_transactions_complete', 'innodb_background_complete', 'innodb_start_complete',
             'plugins_complete', 'ddl_recovery_complete', 'embedded_complete', 'ready_prepared']
    record = {'version': 1, 'clock': 'guest_monotonic', 'dropped_records': 0,
              'events': [{'name': name, 'offset_ns': i*1000, 'process_cpu_ns': i*1500,
                          'thread_cpu_ns': None} for i, name in enumerate(order)], 'files': []}
    report = {'samples': [{'case': 'fork_batch', 'workers': 4, 'phase': 'measurement',
                           'per_db': [{'stage_timings': {'host': {'guest': {'initialization': record}}}}]}]}
    rows = summarize(report)
    row = next(r for r in rows if r['stage'] == 'buffer pool creation')
    assert row['wall_ns']['p50'] == 1000
    assert row['process_cpu_ns']['p50'] == 1500  # CPU may exceed wall across threads.
    assert row['thread_cpu_ns'] is None
    record['events'].pop()
    with pytest.raises(ValueError, match='missing'):
        validate(record)
