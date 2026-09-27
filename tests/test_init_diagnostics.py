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
        assert text.count('mariamem_init_mark(') + text.count('mariamem_init_plugin_mark(') == len(hooks)
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
 char plugin_name[32]="Aria";
 mariamem_init_plugin_mark(plugin_name,"begin");
 strcpy(plugin_name,"mutated");
 mariamem_init_plugin_mark("Aria","end");
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
    start, end = record['events'][0], record['events'][-1]
    assert [event['name'] for event in record['events'][1:3]] == ['plugin.Aria.begin', 'plugin.Aria.end']
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
             'components_begin', 'myisam_key_cache_begin', 'myisam_key_cache_complete', 'plugins_begin', 'innodb_plugin_begin', 'innodb_parameters_complete',
             'innodb_runtime_begin', 'buffer_pool_begin', 'buffer_pool_complete',
             'innodb_memory_background_complete', 'innodb_open_recovery_complete',
             'innodb_transactions_complete', 'innodb_background_complete', 'innodb_start_complete',
             'aria_begin', 'aria_cache_begin', 'aria_cache_complete', 'aria_log_cache_complete',
             'aria_log_init_complete', 'aria_recovery_complete', 'aria_checkpoint_complete', 'aria_complete',
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


def test_plugin_callback_cpu_and_mapping_are_distinct():
    from init_report import INTERVALS
    names = ['guest_main', 'restore_complete', 'ready_prepared'] + list(dict.fromkeys(name for pair in INTERVALS.values() for name in pair))
    # Only relative ordering of each tested plugin callback is relevant here.
    events = [{'name': name, 'offset_ns': 100, 'process_cpu_ns': 101} for name in names]
    last = 100
    # A synthetic callback wholly after existing fixed scopes.
    events.extend([
        {'name': 'plugin.Aria.begin', 'offset_ns': last + 100, 'process_cpu_ns': 100,
         'thread_cpu_ns': 50, 'wrapped_mmap_balance_bytes': 0},
        {'name': 'plugin.Aria.end', 'offset_ns': last + 300, 'process_cpu_ns': 280,
         'thread_cpu_ns': 200, 'wrapped_mmap_balance_bytes': 128 * 1024**2},
    ])
    events.sort(key=lambda event: event['offset_ns'])
    record = {'version': 1, 'clock': 'guest_monotonic', 'dropped_records': 0,
              'events': events, 'files': []}
    report = {'samples': [{'case': 'fork_batch', 'workers': 8, 'phase': 'measurement',
              'per_db': [{'stage_timings': {'host': {'guest': {'initialization': record}}}}]}]}
    row = next(row for row in summarize(report) if row['stage'] == 'plugin Aria callback')
    assert row['wall_ns']['p50'] == 200
    assert row['process_cpu_ns']['p50'] == 180
    assert row['thread_cpu_ns']['p50'] == 150
    assert row['wrapped_mmap_balance_bytes']['p50'] == 128 * 1024**2


def test_aria_short_circuit_marker_is_false_without_call_reordering(tmp_path):
    cc = shutil.which('cc')
    if not cc:
        pytest.skip('native C compiler unavailable')
    source = tmp_path / 'expression.c'
    source.write_text('''static int calls, marks, fail;
void mariamem_init_mark(const char *name) { marks++; }
int step(int n) { calls = calls*10 + n; return fail == n; }
int main(void) {
 for(fail=0; fail<=3; fail++) {
  calls=marks=0; int a=step(1)||step(2)||step(3); int before=calls;
  calls=0;
  int b=(mariamem_init_mark("cache"),0)||step(1)||
        (mariamem_init_mark("log"),0)||step(2)||
        (mariamem_init_mark("recovery"),0)||step(3);
  if(a!=b || calls!=before || marks!=(fail==1?1:fail==2?2:3)) return 1;
 }
 return 0;
}''')
    output = tmp_path / 'expression'
    subprocess.run([cc, '-std=c11', str(source), '-o', str(output)], check=True)
    subprocess.run([str(output)], check=True)
