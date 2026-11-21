"""Classify a stale observation using the independent per-instance route."""
from pathlib import Path
def count(path,name):
    return path['Counters'].get(name,{}).get('Count',0)

def locate(path):
    if path['KeyMismatches']:
        return 'identity mismatch'
    if not path['Old']['Low'] and path['Old']['SinceTickMS']>4000:
        counters=path['Counters']
        if not count(path,'maintenance_return'):
            return 'insufficient completed callback history'
        def pending(enter,leave):
            return count(path,enter)>count(path,leave)
        if pending('maintenance_enter','maintenance_return'):
            return 'maintenance entered without return'
        if pending('execute_enter','execute_return'):
            return 'timer runner entered without return'
        if pending('dispatch','dispatch_done'):
            return 'timer handler dispatch outstanding'
        if pending('reinsert','reinsert_done'):
            return 'reinsertion outstanding'
        if count(path,'handler_return'):
            return 'timer handler exited'
        if count(path,'reinsert_done') and counters['reinsert_done']['Last']['AtNS']>=counters['maintenance_return']['Last']['AtNS']:
            stage=path['Handler']['Kind']
            return 'callback returned and reinserted; handler at '+stage
        if count(path,'old_period_us') and counters['old_period_us']['Last']['Value']==0:
            return 'timer did not have a periodic interval at pop'
        if count(path,'new_period_us') and counters['new_period_us']['Last']['Value']==0:
            return 'timer period cleared after callback'
        return 'unresolved stale observation'
    return 'timely'

def check(r,pilot=False):
    assert r['Armed']==9 and len(r['After'])==8 and r['After']==[[40,100,1888173,1888173]]*8
    assert len(r['Waves'])==(2 if pilot else 9) and len(r['InitialStocks'])==8
    stocks=r['InitialStocks'].copy()
    gaps=[]
    learned={}
    for wave_index,wave in enumerate(r['Waves'],1):
        assert len(wave['Paths'])==len(wave['Wakes'])==8
        gids=set()
        for i,(path,wake) in enumerate(zip(wave['Paths'],wave['Wakes'])):
            assert wake['ID']==path['DB']==i+2
            identity=(path['Timer'],path['Pool'],path['HandlerGID'])
            assert min(identity)>0 and learned.setdefault(i,identity)==identity
            gids.add(path['HandlerGID'])
            assert count(path,'dispatch')>0 and count(path,'execute_enter')>0 and count(path,'maintenance_enter')>0
            assert count(path,'reinsert_done')>0
            assert path['Counters']['dispatch']['Last']['Address']==path['Timer']+8
            assert path['Counters']['dispatch']['Last']['Value']==12334
            assert path['Counters']['maintenance_enter']['Last']['Address']==path['Pool']
            assert path['Counters']['execute_enter']['Last']['Address']==path['Timer']
            delta_ms=(path['NowNS']-path['Counters']['maintenance_enter']['Last']['AtNS'])/1e6
            status=locate(path)
            if status!='timely':
                gaps.append(dict(wave=wave_index,db=i+1,id=path['DB'],status=status,old_age=path['Old']['SinceTickMS'],
                                 route_age=delta_ms,handler=path['Handler'],stack=Path(path['StackFile']).name+'.gz' if path['StackFile'] else ''))
            assert 0<=wake['ConnectMS']<=wake['TotalMS'] and 0<=wake['SQLMS']<=wake['TotalMS']
            stocks[i]+=int(wake['Write'])
        assert len(gids)==8 and sum(w['Write'] for w in wave['Wakes'])==4
    assert stocks==r['FinalStocks']
    return gaps

def resolved(gap):
    return abs(gap['old_age']-gap['route_age'])<5 and gap['status'] not in (
        'unresolved stale observation','insufficient completed callback history','identity mismatch')
