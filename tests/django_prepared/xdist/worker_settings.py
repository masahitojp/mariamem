"""Diagnostic wrapper around the existing authored D1 workload."""
import json
import os
from pathlib import Path
import time

WORKER = os.environ.get('PYTEST_XDIST_WORKER', 'controller')
OUT = Path(os.environ['D1_XDIST_OUTPUT'])
MODE = os.environ.get('D1_XDIST_MODE', 'healthy')
COUNT = int(os.environ.get('D1_DB_WORKERS', '2'))
os.environ['MARIAMEM_PREPARED_EVENTS'] = str(OUT / (WORKER + '.jsonl'))
os.environ['MARIAMEM_PREPARED_MODE'] = 'body-failure' if MODE == 'body-failure' else 'healthy'

from prepared_settings import *  # reuse app, migrations, public SDK trace/entry
import prepared_settings as original

_event = original.event

def event(name, **data):
    _event(name, worker=WORKER, process=os.getpid(), **data)

original.event = event
MARIAMEM_DJANGO_PREPARE = 'worker_settings.prepare'
event('declaration_checked', source_absent=DATABASES['default']['MARIAMEM_PREPARED'].source is None)


def barrier(label):
    source = DATABASES['default']['MARIAMEM_PREPARED'].source
    record = dict(worker=WORKER, host_pid=source.diagnostics['host_pid'], process=os.getpid())
    marker = OUT / (label + '-' + WORKER + '.json')
    temporary = marker.with_suffix('.tmp')
    temporary.write_text(json.dumps(record))
    temporary.replace(marker)
    deadline = time.monotonic() + 20
    while len(list(OUT.glob(label + '-gw*.json'))) != COUNT:
        if time.monotonic() >= deadline:
            raise TimeoutError('xdist overlap barrier timed out: ' + label)
        time.sleep(.01)
    others = [json.loads(p.read_text()) for p in OUT.glob(label + '-gw*.json')]
    for other in others:
        os.kill(other['host_pid'], 0)  # coexistence witness, not memory/timing data
    event('overlap', boundary=label, hosts=sorted(r['host_pid'] for r in others))
    (OUT / (label + '-' + WORKER + '.ack')).touch()
    while len(list(OUT.glob(label + '-gw*.ack'))) != COUNT:
        if time.monotonic() >= deadline:
            raise TimeoutError('xdist overlap acknowledgement timed out: ' + label)
        time.sleep(.01)


def prepare(connection):
    original.prepare(connection)
    with connection.cursor() as cursor:
        cursor.execute('CREATE TABLE worker_seed (worker VARCHAR(16) PRIMARY KEY)')
        cursor.execute('INSERT INTO worker_seed VALUES (%s)', (WORKER,))
        cursor.execute("SELECT name FROM django_migrations WHERE app='orders' ORDER BY name")
        assert list(cursor.fetchall()) == [('0001_initial',), ('0002_status',)]
    source = DATABASES['default']['MARIAMEM_PREPARED'].source
    info = source.connection_info()
    event('prepared', database=connection.settings_dict['NAME'], host_pid=source.diagnostics['host_pid'],
          source_id=source.id, port=info['port'])
    if MODE in ('crash','restart'):
        if WORKER in ('gw0','gw1'):
            barrier('prepare')
        elif MODE == 'restart':
            (OUT/'replacement-ready').touch()
    elif MODE not in ('idle','cleanup-failure'):
        barrier('prepare')
    if MODE == 'prepare-failure' and WORKER == 'gw0':
        raise RuntimeError('XDIST_GW0_PREPARE_FAILURE')


# Observe public consuming capture and fork without inspecting SDK handles.
import mariamem
_snapshot = mariamem.Database.snapshot
_fork = mariamem.Snapshot.fork

def snapshot(self, **options):
    saved = _snapshot(self, **options)
    event('capture', source_id=self.id, consumed=self.closed)
    return saved

def fork(self, **options):
    child = _fork(self, **options)
    event('fork', child_id=child.id, host_pid=child.diagnostics['host_pid'])
    return child

mariamem.Database.snapshot = snapshot
mariamem.Snapshot.fork = fork

if MODE == 'no-restore':
    from mariamem.django._database import Scope
    _acquire = Scope.acquire
    def acquire(self):
        if self.child is None:
            return _acquire(self)
        self.manager.activate(self.child)
    def release(self):
        self.manager.quiesce()  # deliberate mutant: keep changed test child
    Scope.acquire, Scope.release = acquire, release


if MODE == 'cleanup-failure':
    from mariamem.django._database import Scope
    _release = Scope.release
    _failed = False
    def release_with_debt(self):
        global _failed
        if WORKER == 'gw0' and self.child is not None and not _failed:
            self.manager.quiesce()
            _failed = True
            self.manager.owners.debt = True
            event('cleanup_failure', retained_child=True)
            raise RuntimeError('XDIST_CHILD_CLEANUP_FAILURE')
        return _release(self)
    Scope.release = release_with_debt
