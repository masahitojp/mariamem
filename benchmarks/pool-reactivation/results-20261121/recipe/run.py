"""Run one paired campaign. Each fresh process owns its eight live forks."""
import json
import os
from pathlib import Path
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
    for block in range(1,2 if phase=='pilot' else 5):
        order=['current','split'] if block%2 else ['split','current']
        for pos,arm in enumerate(order):
            label=f'{phase}-{block}-{pos}-{arm}'
            report=out/(label+'.json')
            assert not report.exists()
            env=dict(common,BURST_REPORT=str(report),BURST_PILOT=str(int(phase=='pilot')),
                BURST_REVERSE=str(int(block%2==0)),BURST_LONG=f'{69+block}.25s')
            run(arm,label,env,'^$')
            r=json.loads(report.read_bytes())
            assert r['Period']==(400 if arm=='current' else 50) and r['Armed']==9
            assert len(r['Waves'])==(2 if phase=='pilot' else 9)
            assert r['After']==[[40,100,1888173,1888173]]*8
            print(label,'PASS',flush=True)
