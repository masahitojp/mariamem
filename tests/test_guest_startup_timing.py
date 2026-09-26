"""Native C diagnostic smoke; guest execution/AOT is checked by the build workflow."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_guest_diagnostic_is_opt_in_and_monotonic(tmp_path):
    compiler = shutil.which('cc')
    if not compiler:
        pytest.skip('C compiler unavailable')
    source = tmp_path / 'check.c'
    source.write_text('''#include <stdio.h>
#include <stdlib.h>
static const char *destination;
static FILE *diagnostic_open(const char *path, const char *mode) { return fopen(destination, mode); }
#define fopen diagnostic_open
#include "startup_timing.inc"
int main(int argc, char **argv) {
 destination = argv[1];
 startup_mark("disabled"); startup_write();
 if (startup_timing.count) return 1;
 if (argc == 2) return 0;
 startup_timing.enabled = 1;
 startup_mark("guest_main"); startup_mark("restore_complete"); startup_write();
 return 0;
}
''')
    executable = tmp_path / 'check'
    subprocess.run([compiler, '-std=c11', '-D_POSIX_C_SOURCE=200809L', '-DMARIAMEM_DIAGNOSTIC_TEST', '-I', str(ROOT/'guest'),
                    str(source), '-o', str(executable)], check=True)
    result = tmp_path / 'timing.json'
    subprocess.run([str(executable), str(result)], check=True)
    assert not result.exists()
    subprocess.run([str(executable), str(result), 'enabled'], check=True)
    record = json.loads(result.read_text())
    assert record['clock'] == 'guest_monotonic' and record['version'] == 1
    assert [event['name'] for event in record['events']] == ['guest_main', 'restore_complete']
    assert record['events'][0]['offset_ns'] == 0
    assert record['events'][1]['offset_ns'] >= 0
    subprocess.run([str(executable), str(tmp_path/'missing'/'record'), 'enabled'], check=True)
