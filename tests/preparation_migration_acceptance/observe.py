"""Worker-local synthetic acceptance events; never records connection secrets."""
import json
import os
from pathlib import Path


def record(event, **fields):
    worker = os.environ.get('PYTEST_XDIST_WORKER', 'main')
    base = Path(os.environ['MIGRATION_EVENTS'])
    path = base.with_name(f'events-{worker}.jsonl')
    with path.open('a') as out:
        out.write(json.dumps({'event': event, 'worker': worker, **fields}) + '\n')
