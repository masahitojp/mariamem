"""Counters/phase times only; no sleeps or barriers."""
import atexit
import json
import os
import time
from pathlib import Path
import prepared_settings as original
from prepared_settings import *

if os.environ['D1_RESOURCE_PROFILE'] == 'heavy':
    MIGRATION_MODULES = {'orders': 'heavy_migrations'}
worker = os.environ.get('PYTEST_XDIST_WORKER', 'serial')
report = {'worker': worker, 'pid': os.getpid(), 'counts': {}, 'seconds': {}, 'host_pids': [], 'prepare_seconds': None}
original.event = lambda *args, **kwargs: None
origin = None

def wrap(owner, name):
    method = getattr(owner, name)
    def measured(*args, **kwargs):
        global origin
        started = time.perf_counter()
        if name == 'start':
            origin = started
        result = method(*args, **kwargs)
        ended = time.perf_counter()
        report['counts'][name] = report['counts'].get(name, 0) + 1
        report['seconds'][name] = report['seconds'].get(name, 0) + ended-started
        if name == 'start':
            report['host_pids'].append(result.diagnostics['host_pid'])
        if name == 'snapshot' and report['prepare_seconds'] is None:
            report['prepare_seconds'] = ended-origin
        return result
    setattr(owner, name, measured)
import mariamem
wrap(mariamem, 'start')
wrap(mariamem.Database, 'snapshot')
wrap(mariamem.Snapshot, 'fork')

@atexit.register
def save():
    Path(os.environ['D1_TIMING_OUT'], worker+'.json').write_text(json.dumps(report,indent=2)+'\n')
