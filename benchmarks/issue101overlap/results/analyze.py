"""Read-only replay with --check; no discarded temp or raw data dependency."""
from pathlib import Path
import csv
import hashlib
import json
import math
import statistics as st
import sys

ROOT=Path(__file__).resolve().parent
if (ROOT/'compact').exists():ROOT=ROOT/'compact'
def read(n):return json.loads((ROOT/n).read_text())
def q(v):
    v=sorted(v)
    return {'p50':st.median(v),'p95':v[math.ceil(.95*len(v))-1],'max':max(v),'over100ms':sum(x>=100 for x in v)}
def duration(s,n):return float(s[n+'_end_ms'])-float(s[n+'_begin_ms']) if s[n+'_begin_ms']!='' else 0.
def interval(s,n):return (float(s[n+'_begin_ms']),float(s[n+'_end_ms']))
def union_length(intervals):
    total=0;end=-float('inf')
    for a,b in sorted(intervals):
        if b>end:total+=b-max(a,end);end=b
    return total
trials=read('trials.json');children=list(csv.DictReader((ROOT/'children.csv').open()))
assert len(trials)==24
byrun={t['name']:[s for s in children if s['run']==t['name']] for t in trials}
perrun={};stages={}
for t in trials:
    assert t['accepted'] and t['cleanup'] and t['scratch_empty']
    assert t['max_active']<=t['parallel']==t['resolved_max_forks']
    stats=t['cleanup_stats']
    assert all(stats[k]==0 for k in ['active_mappings','active_rw_bytes','active_reserved_bytes','release_failures'])
    assert stats['creates']==stats['releases']
    ss=byrun[t['name']]
    if t['kind']=='negative':assert not t['success'] and 'pristine oracle' in t['error'];continue
    assert t['success'] and all(s['oracle']==s['cleanup']=='True' for s in ss)
    assert len(ss)==(2 if t['kind']=='positive' else 48)
    assert {int(s['index']) for s in ss}==set(range(len(ss)))
    overlaps=[]
    for s in ss:
        a,b=interval(s,'start_or_fork'); intersections=[]
        for other in ss:
            if other is s:continue
            # Connection+SQL and retire+Close intervals. Barrier waits are excluded.
            for c,d in [(float(other['connect_begin_ms']),float(other['verify_update_end_ms'])),(float(other['retire_begin_ms']),float(other['close_end_ms']))]:
                if max(a,c)<min(b,d):intersections.append((max(a,c),min(b,d)))
        overlaps.append(union_length(intersections))
    if t['arm']=='wave':
        p=t['parallel']
        ordered=sorted(ss,key=lambda s:int(s['index']))
        for first in range(0,len(ss),p):
            wave=ordered[first:first+p]
            assert max(float(s['start_or_fork_end_ms']) for s in wave)<=min(float(s['connect_begin_ms']) for s in wave)
            assert max(float(s['verify_update_end_ms']) for s in wave)<=min(float(s['retire_begin_ms']) for s in wave)
            if first:assert max(float(s['close_end_ms']) for s in ordered[first-p:first])<=min(float(s['start_or_fork_begin_ms']) for s in wave)
        assert max(overlaps)==0
    perrun[t['name']]={
        'suite_ms':t['suite_ms'],'batch_ms':t['batch_ms'],'cpu_ms':t['suite_cpu_ms'],'rss_mib':t['lifetime_max_rss_bytes']/2**20,
        'fork':q([duration(s,'start_or_fork') for s in ss]),
        'sql':q([float(s['verify_update_end_ms'])-float(s['connect_begin_ms']) for s in ss]),
        'retire':q([duration(s,'retire') for s in ss]),'close':q([duration(s,'close') for s in ss]),
        'fork_barrier':q([duration(s,'fork_barrier') for s in ss]),'sql_barrier':q([duration(s,'sql_barrier') for s in ss]),
        'fork_overlapping_other_sql_cleanup':q(overlaps),
        'fork_overlap_fraction':sum(overlaps)/sum(duration(s,'start_or_fork') for s in ss),
    }
trace_rows=read('stages.json')
expected={(t['name'],i) for t in trials if t['kind']=='diagnostic' for i in range(48)}
assert len(trace_rows)==192 and {(x['run'],x['index']) for x in trace_rows}==expected
for x in trace_rows:
    events={e['name']:e['offset_ns']/1e6 for e in x['trace']['events']}
    assert x['trace']['operation']=='fork'
    stages.setdefault(x['run'],[]).append(events['startup_returned']-events['snapshot_handle_ready'])
summary={'per_run':perrun,'primary':{},'diagnostic_fork_startup_envelope':{k:q(v) for k,v in stages.items()},
         'diagnostic_limit':'Child callback retains the outer fork trace only; guest server_init unavailable. No per-child server_init attribution from this campaign.'}
for p in [4,8]:
    cells={a:[t for t in trials if t['parallel']==p and t['arm']==a and t['kind']=='primary'] for a in ['mixed','wave']}
    for values in cells.values():assert len(values)==3
    paired=[]
    for rep in range(3):
        m=next(t for t in cells['mixed'] if t['rep']==rep);w=next(t for t in cells['wave'] if t['rep']==rep)
        mm=perrun[m['name']];ww=perrun[w['name']]
        paired.append(dict(rep=rep,suite_delta_ms=w['suite_ms']-m['suite_ms'],suite_percent=(w['suite_ms']/m['suite_ms']-1)*100,fork_p50_delta_ms=ww['fork']['p50']-mm['fork']['p50']))
    summary['primary'][str(p)]={'pairs':paired,'arms':{a:{'suite_median_ms':st.median(t['suite_ms'] for t in ts),'batch_median_ms':st.median(t['batch_ms'] for t in ts),'cpu_median_ms':st.median(t['suite_cpu_ms'] for t in ts),'rss_median_mib':st.median(t['lifetime_max_rss_bytes']/2**20 for t in ts),'fork_p50_run_median_ms':st.median(perrun[t['name']]['fork']['p50'] for t in ts),'fork_p95_run_median_ms':st.median(perrun[t['name']]['fork']['p95'] for t in ts),'overlap_fraction_run_median':st.median(perrun[t['name']]['fork_overlap_fraction'] for t in ts)} for a,ts in cells.items()}}
if '--check' in sys.argv:
    assert summary==read('summary.json')
    for n,h in read('SHA256SUMS.json').items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,n
    print('PASS compact replay, scheduling isolation, SQL/cap/cleanup and hashes')
else:
    (ROOT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary['primary'],indent=2))
    print('DIAGNOSTIC ONLY',json.dumps(summary['diagnostic_fork_startup_envelope'],indent=2))
