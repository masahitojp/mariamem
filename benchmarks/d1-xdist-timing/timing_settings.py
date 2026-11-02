"""Benchmark-only settings; accumulate public SDK counters without barriers."""
import atexit
import json
import os
import time
from pathlib import Path
import prepared_settings as original
from prepared_settings import *

worker = os.environ.get('PYTEST_XDIST_WORKER', 'serial')
report = {'worker': worker, 'pid': os.getpid(), 'counts': {}, 'seconds': {}, 'host_pids': []}
def event(*args, **kwargs):
    pass
original.event = event

def wrap(owner, name):
    method = getattr(owner, name)
    def measured(*args, **kwargs):
        started = time.perf_counter()
        result = method(*args, **kwargs)
        report['counts'][name] = report['counts'].get(name, 0) + 1
        report['seconds'][name] = report['seconds'].get(name, 0) + time.perf_counter() - started
        if name == 'start':
            report['host_pids'].append(result.diagnostics['host_pid'])
        return result
    setattr(owner, name, measured)

import mariamem
wrap(mariamem, 'start')
wrap(mariamem.Database, 'snapshot')
wrap(mariamem.Snapshot, 'fork')

@atexit.register
def save():
    Path(os.environ['D1_TIMING_OUT'], worker + '.json').write_text(json.dumps(report, indent=2)+'\n')
