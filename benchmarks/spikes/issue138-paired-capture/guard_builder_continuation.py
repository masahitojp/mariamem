#!/usr/bin/env python3
"""Count every task-owned mounted path, guard the canonical child, save stats."""
import json
from pathlib import Path
import sys
import time

repo = Path('/repo')
sys.path.insert(0, str(repo / 'scripts'))
from experiment_disk import DiskGuard, run_guarded

guard = DiskGuard(Path('/owned'), 6, 24)
assert guard.floor == 6 * (1 << 30) and guard.budget == 24 * (1 << 30)
initial = guard.check()
start = time.monotonic()
code = 1
error = None
try:
    code = run_guarded([sys.executable, str(repo / 'benchmarks/spikes/issue128-real/build_checked.py')],
                       guard, timeout=3600, interval=2)
except BaseException as exc:
    error = {'exception': type(exc).__name__, 'message': str(exc)}
    raise
finally:
    Path('/output/disk-result.json').write_text(json.dumps({
        'initial': initial, 'peak_owned_bytes': guard.peak,
        'minimum_free_bytes': guard.minimum_free, 'exit': code, 'error': error,
        'wall_seconds': time.monotonic() - start,
        'scope': '/owned contains every task-owned download, source, SDK, compiler cache, temp, work and output mount'}, indent=2) + '\n')
raise SystemExit(code)
