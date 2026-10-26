"""Opt-in child-process diagnostics; never imported by the product SDK."""
import os

if os.environ.get('E2E_CHILD_DIAGNOSTICS') == '1':
    import faulthandler
    import sys

    print(f'E2E_CHILD_DIAGNOSTICS pid={os.getpid()} python={sys.version}',
          file=sys.stderr, flush=True)
    # Two stack snapshots fit inside the unchanged 30-second app startup gate.
    # The process owns this timer; it changes no SQL, app checks or timeouts.
    faulthandler.enable()
    faulthandler.dump_traceback_later(10, repeat=True)
