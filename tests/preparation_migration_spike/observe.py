"""Experiment-only JSON event stream; contains synthetic fixture data only."""
import json
import os
from pathlib import Path


def record(event, **fields):
    with Path(os.environ['MIGRATION_EVENTS']).open('a') as out:
        out.write(json.dumps({'event': event, **fields}) + '\n')
