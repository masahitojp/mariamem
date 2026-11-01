"""One real SDK source per runner invocation, before Django loads settings."""
import atexit
import json
import os
from pathlib import Path
import sys
import mariamem

source = mariamem.start()
session = source._session  # Diagnostic observation only; owner operations use SDK.
metadata = dict(host_pid=source.diagnostics['host_pid'],root=str(session.root),
                sdk=mariamem.__file__,source_commit='b3b3b46a8807482ad3f96725af86e031fe369b01')
receipt = Path(os.environ['D1_SCRATCH'])/'host.json'
receipt.write_text(json.dumps(metadata)+'\n')

def finalize():
    try:
        source.close()
    finally:
        entry = sys.modules.get('entry')
        registry = getattr(getattr(entry,'RealOwner',None),'registry',[])
        metadata.update(open_owners=[v.label for v in registry if not v.closed],
                        host_reaped=session._reaped.is_set(),root_removed=not session.root.exists())
        receipt.write_text(json.dumps(metadata)+'\n')

atexit.register(finalize)
