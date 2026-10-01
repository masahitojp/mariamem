#!/usr/bin/env python3
"""Compact prepared-clone evidence; full hashes/stacks/mappings stay local."""
import argparse
import json
from pathlib import Path
import re

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--results',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
report={'schema_version':1,'source_sha':'8658310fce7745c7a8df04bc0aed7d7a6ce5ce14','date':'2026-10-01',
 'environment':{'cpu':'Apple M1','ram_bytes':17179869184,'os':'macOS 27.0 (26A428)','page_bytes':16384,'go':'go1.26.8'},'captures':[]}
for name in ['capture','capture-repeat-1']:
 r=json.loads((a.results/name/'capture.json').read_text())
 if r['innodb_status'].get('ok'):
  status=bytes.fromhex(r['innodb_status']['rows'][0][2]['$h']).decode()
  r['innodb_status_text']=status;r.pop('innodb_status')
 stacks=json.loads((a.results/name/'live-3.json').read_text())['runtime']['goroutine_stacks']
 r['goroutine_states']=[s.splitlines()[0] for s in stacks.split('\n\n') if s.startswith('goroutine ')]
 r['guest_stack_functions']=sorted(set(re.findall(r'example.com/mariamem-spike/[^\s(]+',stacks)))
 report['captures'].append(r)
report['measurement']=json.loads((a.results/'measure/results.json').read_text())
report['mapping']={}
for mode in ['fresh','anon','cow']:
 data=[]
 for name in ['summary','regions']:
  for line in (a.results/'mapping'/mode/(name+'.vmmap')).read_text().splitlines():
   if name=='summary' and line.startswith(('Physical footprint','Untagged','mapped file','Stack ','TOTAL ')):data.append(line)
   if name=='regions' and (line.endswith('/memory.bin') or '/capture/base/' in line):
    suffix='<initialized-linear>' if line.endswith('/memory.bin') else '<prepared-base>/'+line.split('/capture/base/')[1]
    data.append(re.sub(r'\s+/.*$',' '+suffix,line))
 report['mapping'][mode]=data
a.output.write_text(json.dumps(report,indent=2)+'\n')
