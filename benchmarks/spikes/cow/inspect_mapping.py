#!/usr/bin/env python3
"""Inspect matched ready mappings; OS counters precede any content observation."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).parent))
from characterize import Guest,get

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--binary',type=Path,required=True)
p.add_argument('--image',type=Path,required=True)
p.add_argument('--helper',type=Path,required=True)
p.add_argument('--output-dir',type=Path,required=True)
a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=True)
report={}
for mode in ['fresh','anon','cow']:
    d=a.output_dir/mode;d.mkdir(exist_ok=True)
    env=dict(os.environ,COW_CONTROL_DIR=str(d.resolve()),COW_LINEAR_MODE=mode,COW_LINEAR_IMAGE=str(a.image.resolve()))
    with (d/'guest.log').open('wb') as log:
        g=Guest([str(a.binary.resolve()),'measure'],log,env=env)
        try:
            assert g.frame()['result']['ready'];assert g.call(1)['ok'];assert g.call(2,'SELECT 1')['ok']
            pid=g.proc.pid
            counters=json.loads(subprocess.check_output([str(a.helper.resolve()),str(pid)],text=True))[str(pid)]
            for name,args in [('summary',['-summary','-wide']),('regions',['-wide'])]:
                r=subprocess.run(['vmmap',*args,str(pid)],capture_output=True,text=True,check=True)
                (d/(name+'.vmmap')).write_text(r.stdout+r.stderr)
            control=json.loads((d/'control.json').read_text())
            s=get(control['port'],'sample');s['os_before_observer']=counters;report[mode]=s
            assert g.call(3)['closed'];assert g.stop()==0
        finally:
            if g.proc.poll() is None:g.proc.kill();g.proc.wait()
(a.output_dir/'results.json').write_text(json.dumps(report,indent=2)+'\n')
print('all modes inspected')
