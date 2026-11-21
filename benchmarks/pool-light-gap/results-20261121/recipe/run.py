"""Run one paired campaign. Each fresh process owns its eight live forks."""
import json
import os
from pathlib import Path
from check import validate
import subprocess
import sys

w=Path(sys.argv[1]).resolve()
phase=sys.argv[2]
tmp=w/'temp'
out=w/'evidence/study'
common={k:os.environ[k] for k in ('HOME','PATH')}
common.update(TMPDIR=str(tmp/'gotmp'),GOGC='100',GOMAXPROCS='8',MODELCASE_MATCHED='1',
              REVENUE_PREAGG='1',MARIA_AUDIT_OF='1',MARIA_ASYNC_CLOSE='0',SKIP_READ_BODY='0',TRANSPORT_DIAG='0')
def run(arm,label,env,pattern):
    p=subprocess.run([tmp/(arm+'.test'),'-test.run='+pattern,'-test.v','-test.timeout=180s'],
                     env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=185)
    if p.returncode or '--- SKIP:' in p.stdout:
        (out/('failed-'+label+'.log')).write_text(p.stdout)
        raise RuntimeError(label+' '+p.stdout[-1800:])
    return p.stdout
if phase=='smoke':
    log=run('plain','plain-smoke',common,'^TestMatchedSemantics$')
    assert '--- PASS: TestMatchedSemantics' in log
    print(log,flush=True)
else:
    assert phase in ('pilot','main')
    for block in range(1,2 if phase=='pilot' else 13):
        order=['current','split'] if block%2 else ['split','current']
        for pos,arm in enumerate(order):
            label=f'{phase}-{block}-{pos}-{arm}'
            report=out/(label+'.json')
            assert not report.exists()
            env=dict(common,BURST_REPORT=str(report),BURST_PILOT=str(int(phase=='pilot')),
                BURST_REVERSE=str(int(block%2==0)),BURST_LONG=f'{70+(block-1)%4}.25s')
            run(arm,label,env,'^$')
            r=validate(report,arm,block,phase=='pilot')
            captured=r['Monitor']['Captured']
            print(label,'PASS','capture',captured,flush=True)
            if phase=='main' and captured:
                sys.exit(0)
