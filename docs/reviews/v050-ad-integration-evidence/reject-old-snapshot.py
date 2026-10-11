import json
from pathlib import Path
import sys
import mariamem

old, host = map(Path, sys.argv[1:])
try:
    snapshot = mariamem.load_snapshot(old, host_binary=host)
except (ValueError, mariamem.HostError) as exc:
    assert 'snapshot wasm build mismatch' in str(exc).lower(), str(exc)
    print(json.dumps({'result':'PASS', 'error_type':type(exc).__name__, 'error':str(exc),
                      'old_guest_sha256':json.loads((old/'manifest.json').read_text())['wasm_sha256']}, indent=2))
else:
    snapshot.close()
    raise AssertionError('old guest snapshot was accepted')
