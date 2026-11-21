"""Replay correctness controls and three ordered triplets, one process at a time."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

def verify(data):
    reqs = data['Requests']
    assert [(r['DB'],r['Ordinal'],r['SQL']) for r in reqs] == [
        (db,i,1) for db in range(8) for i in range(100)]
    c = data['Controls']
    assert c['PageSize'] > 0 and c['Numer'] > 0 and c['Denom'] > 0
    for name,rows in c['Rows'].items():
        assert len(rows)==128
        if name.endswith('empty'):
            assert all((r['Before']^r['After']) & (1|8|32|128)==0 for r in rows)
        if name.endswith('second'):
            assert all(r['Before']&1 and r['After']&1 for r in rows)
    for req in reqs:
        for event in req['Events'] or []:
            if event['Kind']=='store':
                queried = req['DB'] in (0,3,5,6)
                assert (event['Before'] >= 0) == queried and (event['After'] >= 0) == queried
                assert event['Guest'] == event['HostPage']*c['PageSize']+event['InPage']
            if event['Site']:
                assert event['Key'] and event['Plan'] and event['Trigger']
                if event['Kind']=='store':
                    assert event['Root'] > 0 and 0 < event['My'] <= event['Wrap'] == event['DL']

def main():
    workspace = Path(sys.argv[1]).resolve()
    temp = workspace/'temp'
    binary = temp/'probe'
    dest = workspace/'evidence/published/runs'
    dest.mkdir(parents=True,exist_ok=True)
    env = dict(os.environ,GOMAXPROCS='8',GOGC='100',TMPDIR=str(temp/'gotmp'))
    (dest/'environment.json').write_text(json.dumps(dict(
        go=subprocess.check_output(['go','version','-m',binary],text=True),
        cpu=subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),
        host=platform.platform(),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
        GOMAXPROCS=8,GOGC=100,parallel_databases=1),indent=2)+'\n')
    for group,order in [('validate','ABC'),('1','ABC'),('2','BCA'),('3','CAB')]:
        for arm in order:
            name=group+'-'+arm
            path=temp/(name+'.json')
            env['TRACE_OUTPUT']=str(path)
            begin=time.monotonic()
            with (dest/(name+'.jsonl')).open('w') as out:
                subprocess.run([binary,'-arm',arm],env=env,stdout=out,check=True)
            verify(json.loads(path.read_bytes()))
            (dest/(name+'.json.gz')).write_bytes(gzip.compress(path.read_bytes(),mtime=0))
            print(name,'pass',round(time.monotonic()-begin,3),flush=True)
if __name__=='__main__':
    main()
