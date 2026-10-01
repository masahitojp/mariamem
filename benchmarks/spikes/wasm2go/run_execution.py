#!/usr/bin/env python3
"""Retain a bounded diagnostic execution (not a startup benchmark)."""
import argparse
import base64
import json
from pathlib import Path
import subprocess
import time


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary', type=Path, required=True)
    p.add_argument('--stage', choices=('instantiate', 'shim-check', 'auth-check', 'start'), required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--timeout', type=float, default=60)
    a = p.parse_args()
    cmd = [str(a.binary.resolve())]
    if a.stage != 'start':
        cmd.append(a.stage)
    started = time.monotonic()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    timed_out = False
    try:
        # Existing guest protocol: zero-length frame requests clean shutdown.
        out, err = proc.communicate(b'\0' * 4, timeout=a.timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        out, err = proc.communicate()
    row = dict(stage=a.stage, seconds=time.monotonic() - started,
               exit_code=proc.returncode, timed_out=timed_out,
               stdout_base64=base64.b64encode(out).decode(),
               stderr=err.decode(errors='replace'))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(row, indent=2) + '\n')
    print(json.dumps(row, indent=2))


if __name__ == '__main__':
    main()
