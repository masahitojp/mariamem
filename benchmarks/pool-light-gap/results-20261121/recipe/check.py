"""Validate one recorded process against its workload and detector binding."""
import json
from pathlib import Path

def validate(report,arm,block,pilot):
    r=json.loads(report.read_bytes())
    assert r['Period']==(400 if arm=='current' else 50) and r['Armed']==9
    assert r['After']==[[40,100,1888173,1888173]]*8
    assert len(r['InitialStocks'])==8 and len(r['Waves'])==(2 if pilot else 9)
    stocks=r['InitialStocks'].copy()
    for i,w in enumerate(r['Waves']):
        want=[.1,.2][i] if pilot else (8 if i<8 else 70.25+(block-1)%4)
        assert w['IdleSeconds']==want and abs(w['AfterIdle']['Seconds']-w['BeforeIdle']['Seconds']-want)<1
        assert len(w['Wakes'])==8 and w['AllResponsesMS']==max(v['EndMS'] for v in w['Wakes'])
        for j,v in enumerate(w['Wakes']):
            assert v['ID']==2+j and v['Write']==((j%2==1) != ((i%2==1) != (block%2==0)))
            assert v['TotalMS']>=v['SQLMS']>=0 and v['TotalMS']>=v['ConnectMS']>=0
            stocks[j]+=v['Write']
    assert stocks==r['FinalStocks']
    m=r['Monitor'];s=m['Last']
    assert m['Scans']>=1 and len(s)==8 and len(set(v['HandlerID'] for v in s))==8
    assert all(v['HandlerID']>0 and v['Entered']>0 and v['Exited']>0 and v['Inserted']>0 for v in s)
    cap=Path(str(report)+'.capture.json')
    assert cap.exists()==m['Captured']
    if m['Captured']:
        v=json.loads(cap.read_bytes())
        assert 2<=v['PoolID']<=9 and not v['Before']['Low']
        assert v['Before']['AtNS']-max(v['Before']['LastEntryNS'],v['Before']['ActiveSinceNS'])>=4e9
        assert v['Before']['HandlerID']==s[v['PoolID']-2]['HandlerID']
        assert Path(str(report)+'.stacks').exists()
        assert Path(str(report)+'.handler').exists()==v['HandlerPresent']
    return r
