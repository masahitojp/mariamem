"""Compact complete-suite timelines and read-only analysis, no build/temp dependency."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import statistics

PHASES=['start_or_fork','connect','version','select1','seed','count_sum','update','verify_update','retire','close','root_start','root_connect','root_seed','root_retire','snapshot','root_close','final_root_retire','final_root_close','snapshot_close']
SQL={'version','select1','count_sum','update','verify_update'}
def ns(ms):return round(ms*1e6)
def encode(r):
    out={k:v for k,v in r.items() if k not in ('samples','root_spans')}
    out['root']=[[PHASES.index(x['name']),ns(x['begin_ms']),ns(x['end_ms'])] for x in r['root_spans']]
    out['cases']=[[s['index'],s['lane'],ns(s['begin_ms']),ns(s['end_ms']),s['oracle'],s['cleanup'],s.get('error',''),s.get('version',''),[[PHASES.index(x['name']),ns(x['begin_ms']),ns(x['end_ms'])] for x in s['spans']]] for s in r['samples']]
    return out

def inspect(r,negative=False):
    assert r['cleanup'] and not r['scratch_remaining'] and r['max_active']<=r['parallel']
    if negative:assert not r['success'] and r['exit_code']==1 and 'pristine oracle' in r['error']
    else:assert r['success'] and r['exit_code']==0 and len(r['cases'])==r['count']
    if r.get('cleanup_stats'):
        assert all(r['cleanup_stats'][k]==0 for k in ('active_mappings','active_rw_bytes','active_reserved_bytes','release_failures'))
    assert len({s[0] for s in r['cases']})==len(r['cases'])
    if not negative:assert sorted(s[0] for s in r['cases'])==list(range(r['count']))
    by_lane={};slow=[];seed_slow=[];values={k:[] for k in PHASES[:10]}
    for i,l,b,e,oracle,cleanup,error,version,spans in r['cases']:
        assert 0<=l<r['parallel'] and b<=e and cleanup
        if not negative:assert oracle and not error
        names=[PHASES[k] for k,_,_ in spans]
        assert len(set(names))==len(names)
        if not negative:assert {'start_or_fork','connect','select1','count_sum','update','verify_update','retire','close'}<=set(names)
        if not negative:assert ('seed' in names)==(r['mode']=='fresh')
        previous=b
        for k,a,z in spans:
            assert previous<=a<=z<=e
            previous=z;name=PHASES[k];values[name].append((z-a)/1e6)
            if name in SQL and z-a>100_000_000:slow.append({'index':i,'lane':l,'phase':name,'ms':(z-a)/1e6})
            if name=='seed' and z-a>100_000_000:seed_slow.append({'index':i,'ms':(z-a)/1e6})
        by_lane.setdefault(l,[]).append((b,e,spans))
    for cases in by_lane.values():
        ordered=sorted(cases)
        assert all(a[1]<=b[0] for a,b in zip(ordered,ordered[1:])), 'overlapping cases within worker'
    if negative:return
    assert r['max_active']<=r['parallel'] and ns(r['batch_end_ms'])-ns(r['batch_begin_ms'])==ns(r['batch_ms'])
    critical=max(by_lane,key=lambda l:max(c[1] for c in by_lane[l]))
    costs={name:0 for name in PHASES[:10]}
    for _,_,spans in by_lane[critical]:
        for k,b,e in spans:costs[PHASES[k]]+=e-b
    budget={k:v/1e6 for k,v in costs.items()}
    budget['gaps_and_join']=(ns(r['batch_ms'])-sum(costs.values()))/1e6
    assert budget['gaps_and_join']>=-0.000001
    assert abs(sum(budget.values())-r['batch_ms'])<0.000002
    def pct(v,p):return sorted(v)[int(p*(len(v)-1))]
    return {'suite_ms':r['suite_ms'],'external_process_ms':r['external_process_ms'],'prepare_ms':r['batch_begin_ms'],'batch_ms':r['batch_ms'],'final_cleanup_ms':r['suite_ms']-r['batch_end_ms'],
            'cpu_ms':r['suite_cpu_ms'],'batch_cpu_ms':r['batch_cpu_ms'],'lifetime_peak_rss_mib':r['lifetime_max_rss_bytes']/1048576,
            'phase_stats_ms':{k:{'p50':statistics.median(v),'p95':pct(v,.95),'max':max(v)} for k,v in values.items() if v},
            'sql_over_100ms':slow,'seed_over_100ms':seed_slow,
            'critical_lane':critical,'critical_lane_cases':len(by_lane[critical]),'critical_lane_budget_ms':budget,
            'root_ms':{PHASES[k]:(e-b)/1e6 for k,b,e in r['root']}}

def summarize(compact):
    runs=compact['runs'];primary={name:inspect(r) for name,r in runs.items() if name.startswith('r')}
    assert len(primary)==36
    for name,r in runs.items():inspect(r,name.startswith('negative-'))
    groups={}
    for backend in ('mariamem','pgmem'):
      for mode in ('fresh','fork'):
       for p in (1,4,8):
        names=[f'r{i}-{backend}-{mode}-p{p}' for i in range(3)];cells=[primary[n] for n in names]
        metrics={k:{'p50':statistics.median(c[k] for c in cells),'all':[c[k] for c in cells]} for k in ('suite_ms','external_process_ms','prepare_ms','batch_ms','final_cleanup_ms','cpu_ms','batch_cpu_ms','lifetime_peak_rss_mib')}
        representative=sorted(names,key=lambda n:primary[n]['external_process_ms'])[1]
        metrics.update({'representative_run':representative,'critical_lane_budget_ms':primary[representative]['critical_lane_budget_ms'],
         'sql_over_100ms_count':sum(len(c['sql_over_100ms']) for c in cells),'seed_over_100ms_count':sum(len(c['seed_over_100ms']) for c in cells),
         'phase_process_medians_ms':{phase:[c['phase_stats_ms'][phase]['p50'] for c in cells] for phase in cells[0]['phase_stats_ms']}})
        groups[f'{backend}-{mode}-p{p}']=metrics
    return {'cells':groups,'runs':primary,'unit':'milliseconds except explicitly named MiB; process repetitions, no tail removal'}

def controls(c):
    for kind in ('missing_case','hidden_oracle','overlap'):
      bad=copy.deepcopy(c['runs']['r0-mariamem-fork-p4'])
      if kind=='missing_case':bad['cases'].pop()
      elif kind=='hidden_oracle':bad['cases'][0][4]=False
      else:bad['cases'][0][8][1][1]=bad['cases'][0][8][0][1]-1
      try:inspect(bad)
      except (AssertionError,KeyError):pass
      else:raise AssertionError('accepted '+kind)

def main():
    p=argparse.ArgumentParser();p.add_argument('--collect',type=Path);p.add_argument('--results',type=Path,required=True);p.add_argument('--check',action='store_true');a=p.parse_args();d=a.results
    if a.collect:
        assert not a.check;d.mkdir(exist_ok=True,parents=True)
        selected=[]
        for pattern in ('r[012]-*.json','warmup-*.json','pilot-*-*.json','negative-*.json'):selected.extend(a.collect.glob(pattern))
        runs={f.stem:encode(json.loads(f.read_text())) for f in sorted(set(selected))}
        assert len(runs)==56,len(runs)
        compact={'schema':1,'case_columns':['index','lane','begin_ns','end_ns','oracle','cleanup','error','version','spans'],'span_columns':['phase_id','begin_ns','end_ns'],'phases':PHASES,'raw_sha256':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(set(selected))},'runs':runs}
        (d/'compact.json').write_text(json.dumps(compact,separators=(',',':'))+'\n')
    c=json.loads((d/'compact.json').read_text());assert c['phases']==PHASES
    controls(c);s=summarize(c)
    if a.check:
        assert json.loads((d/'summary.json').read_text())==s,'summary differs'
        for name,sha in json.loads((d/'SHA256SUMS.json').read_text()).items():assert hashlib.sha256((d/name).read_bytes()).hexdigest()==sha,name
        print('PASS: read-only reduction, 56 process oracles, critical-lane budgets, checksums, 3 negative analysis mutations')
    else:(d/'summary.json').write_text(json.dumps(s,indent=2)+'\n')
if __name__=='__main__':main()
