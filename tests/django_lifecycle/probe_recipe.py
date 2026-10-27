"""Observe the runnable recipe's real owner, without adding user-facing hooks."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import mariamem

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('django_recipe', ROOT / 'docs/examples/django/run_tests.py')
recipe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recipe)
original = mariamem.start
owners = []


def observe(**kwargs):
    source = original(**kwargs)
    owners.append(source)
    return source


mariamem.start = observe
try:
    code = recipe.main(sys.argv[1:])
finally:
    assert len(owners) == 1
    source = owners[0]
    session = source._session
    observed = dict(host_reaped=session._process.poll() is not None,
                    temp_removed=not session.root.exists(), source_closed=source.closed)
    Path(os.environ['W3_RECIPE_RECEIPT']).write_text(json.dumps(observed, indent=2) + '\n')
    assert all(observed.values()), observed
raise SystemExit(code)
