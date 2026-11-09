"""Print summaries from compact evidence. --check compares without writing."""
import json,math,pathlib,statistics as st,sys
p=pathlib.Path(__file__).parent
rows=[r for r in json.loads((p/'observations.json').read_text()) if r['kind']=='natural']
assert len(rows)==10 and all(r['result']=='PASS' for r in rows)
def dist(x):
 return {'n':len(x),'p50':st.median(x),'p95':sorted(x)[math.ceil(.95*len(x))-1],'ge100':sum(v>=100 for v in x)}
def scalar(r):
 return {'wall_ms':r['whole_wall_ms'],'cpu_ms':float(r['meta']['cpu_ms']),'peak_rss_mib':float(r['meta']['maxrss_bytes_darwin'])/2**20,'cleanup_sum_ms':sum(r['cleanup_ms']),'sample_sum_ms':sum(r['sample_ms'])}
s={'arms':{},'pairs':[]}
for arm in (1,4):
 rr=[r for r in rows if r['read_threads']==arm];m=[scalar(r) for r in rr];a={}
 for key in m[0]:
  x=[v[key] for v in m];med=st.median(x);a[key]={'p50':med,'min':min(x),'max':max(x),'MAD':st.median(abs(v-med) for v in x)}
 for key in ('fork_ms','prepare_ms'):a[key]=dist([v for r in rr for v in r[key]])
 s['arms'][str(arm)]=a
for pair in range(5):
 a,b=(scalar(next(r for r in rows if r['pair']==pair and r['read_threads']==arm)) for arm in (1,4))
 s['pairs'].append({'pair':pair,'read1':a,'read4':b,'wall_change_ms':b['wall_ms']-a['wall_ms']})
s['read4_wins']=sum(r['wall_change_ms']<0 for r in s['pairs'])
s['median_change_percent']={k:100*(s['arms']['4'][k]['p50']/s['arms']['1'][k]['p50']-1) for k in ('wall_ms','cpu_ms','peak_rss_mib')}
s['screening_threshold_met']=s['median_change_percent']['wall_ms']<=-5 and s['read4_wins']>=4
if '--check' in sys.argv:
 assert s==json.loads((p/'summary.json').read_text());print('PASS: read-only summary regeneration')
else: print(json.dumps(s,indent=2,sort_keys=True))
