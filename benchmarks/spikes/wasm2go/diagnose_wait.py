#!/usr/bin/env python3
"""Capture a Go stack during a slow diagnostic boot; intentionally interrupts it."""
import argparse
import json
from pathlib import Path
import select
import signal
import subprocess
import time

from sql_execution import Guest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--attempts',type=int,default=30)
    a = p.parse_args()
    a.output_dir.mkdir(parents=True,exist_ok=True)
    rows=[]
    for i in range(a.attempts):
        with (a.output_dir/f'stack-{i}.log').open('wb') as log:
            g = Guest([str(a.binary.resolve())],log)
            try:
                ready = bool(select.select([g.proc.stdout],[],[],.2)[0])
                if ready:
                    assert g.frame()['result']['ready']
                    assert g.call(1)['ok'] and g.call(2,'SELECT 1')['ok']
                    time.sleep(.1)
                    assert g.stop() == 0
                    rows.append(dict(trial=i,ready_within_200ms=True))
                else:
                    g.proc.send_signal(signal.SIGQUIT)
                    rows.append(dict(trial=i,ready_within_200ms=False,
                                     diagnostic_sigquit_exit=g.proc.wait(timeout=10)))
            finally:
                if g.proc.poll() is None: g.proc.kill();g.proc.wait()
                g.proc.stdin.close();g.proc.stdout.close()
        (a.output_dir/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
        if not ready: break


if __name__ == '__main__':main()
