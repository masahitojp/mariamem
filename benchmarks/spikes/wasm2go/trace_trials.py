#!/usr/bin/env python3
"""Collect complete successful fast/slow startup traces, without interrupting waits."""
import argparse
import json
import os
from pathlib import Path
import time
from sql_execution import Guest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--attempts',type=int,default=100)
    p.add_argument('--slow-target',type=int,default=3)
    a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=True)
    rows=[]
    for i in range(a.attempts):
        env=os.environ.copy();env['MARIAMEM_SPIKE_TRACE']=str((a.output_dir/f'trace-{i}.json').resolve())
        with (a.output_dir/f'trace-{i}.log').open('wb') as log:
            started=time.perf_counter();g=Guest([str(a.binary.resolve()),'measure'],log,env=env)
            try:
                assert g.frame()['result']['ready'];ready=time.perf_counter()-started
                assert g.call(1)['ok'] and g.call(2,'SELECT 1')['ok'];sql=time.perf_counter()-started
                assert g.call(3)['closed'];assert g.stop()==0
                rows.append(dict(trial=i,ready_seconds=ready,sql_seconds=sql,slow=ready>=.5))
            finally:
                if g.proc.poll() is None:g.proc.kill();g.proc.wait()
                g.proc.stdin.close();g.proc.stdout.close()
        (a.output_dir/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
        print(rows[-1],flush=True)
        if sum(r['slow'] for r in rows)>=a.slow_target:break


if __name__=='__main__':main()
