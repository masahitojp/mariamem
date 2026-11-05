from pathlib import Path
import json,statistics as st,csv,io,sys,copy
E=Path(__file__).resolve().parent
read=lambda n:json.loads((E/n).read_text())
variants=['both-off','commit0','commit0-method']
metrics=['fork_ms','sql_ms','count_ms','update_ms','check_ms','cleanup_ms','retire_ms','wait_ms','close_ms']
def q(v,p):
 v=sorted(v);i=(len(v)-1)*p;a=int(i);return v[a]+(v[min(a+1,len(v)-1)]-v[a])*(i-a)
def reduce(records):
 inputs=read('inputs.json');rr=[r for r in records if r['repetition']>=0];assert len(rr)==30
 rows=[];cells=[];contrasts=[];slow=[]
 for p in [4,8]:
  arms={}
  for v in variants:
   runs=sorted([r for r in rr if r['parallel']==p and r['variant']==v],key=lambda r:r['repetition']);assert len(runs)==5 and {r['repetition'] for r in runs}==set(range(5));rv=[];pooled=[]
   for r in runs:
    d=read(r['report']);m=read(r['memory']);assert r['binary_sha256']==inputs['binary_sha256'] and r['returncode']==0 and d['success'] and d['cleanup_complete'] and d['root_closed_before_forks'] and d['route']=='pipe' and d['parallel']==p and m['peak_active_children']==p
    ss=d['samples'];assert len(ss)==48 and {x['index'] for x in ss}==set(range(48)) and all(x['oracle'] and x['cleanup_complete'] and not x.get('config') for x in ss) and not d.get('config')
    assert all(all(x[k]>=0 for k in metrics) and x['retire_ms']+x['wait_ms']+x['close_ms']<=x['cleanup_ms']+.02 for x in ss)
    row={'parallel':p,'variant':v,'round':r['repetition'],'batch_ms':d['batch_ms'],'cpu_ms':d['cpu_user_ms']+d['cpu_system_ms'],'peak_rss_mib':m['sampled_peak_rss_bytes']/2**20}
    for k in metrics:
     values=[x[k] for x in ss]
     for name,val in [('p50',st.median(values)),('p95',q(values,.95)),('max',max(values)),('over100',sum(x>100 for x in values)),('over500',sum(x>500 for x in values))]:row[k+'_'+name]=val
    rows.append(row);rv.append(row);pooled+=ss
    for x in ss:
     if x['sql_ms']>100:slow.append({'parallel':p,'variant':v,'round':r['repetition'],**{k:x[k] for k in ['index']+metrics}})
   arms[v]=rv;cell={'parallel':p,'variant':v,'children':240}
   for k in rv[0]:
    if k not in ['parallel','variant','round']:cell[k+'_median']=st.median(x[k] for x in rv)
   for k in metrics:
    values=[x[k] for x in pooled];cell[k+'_pooled']={'p50':st.median(values),'p95':q(values,.95),'max':max(values),'over100':sum(x>100 for x in values),'over500':sum(x>500 for x in values)}
   cells.append(cell)
  for a,b in [('both-off','commit0'),('commit0','commit0-method'),('both-off','commit0-method')]:
   pairs=[]
   for aa,bb in zip(arms[a],arms[b]):
    row={'round':aa['round']}
    for k in ['batch_ms','cpu_ms','fork_ms_p50','update_ms_p50','close_ms_p50','cleanup_ms_p50']:row[k+'_saved_percent']=100*(1-bb[k]/aa[k])
    row['rss_added_mib']=bb['peak_rss_mib']-aa['peak_rss_mib'];pairs.append(row)
   c={'parallel':p,'baseline':a,'candidate':b,'pairs':pairs}
   for k in pairs[0]:
    if k!='round':c[k+'_median']=st.median(x[k] for x in pairs)
   c['guard']=all(c[k+'_saved_percent_median']>=-5 for k in ['batch_ms','cpu_ms','fork_ms_p50'])
   c['benefit_signal']=any(c[k+'_saved_percent_median']>=5 and sum(x[k+'_saved_percent']>0 for x in pairs)>=4 for k in ['batch_ms','update_ms_p50'])
   contrasts.append(c)
 return {'cells':cells,'contrasts':contrasts,'slow_sql':slow,'interpretation':'Blocked three-arm sample, same binary; client spans are not engine queue attribution. Natural rare wait absence is not cure/frequency proof. No adoption or durability claim.'},rows
assert read('complete.json')['result']=='PASS' and read('preflight.json')['result']=='PASS' and read('literal-rejection.json')['result']=='PASS'
result,rows=reduce(read('records.json'));buf=io.StringIO();w=csv.DictWriter(buf,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
if '--check' in sys.argv:
 assert result==read('summary.json') and buf.getvalue()==(E/'processes.csv').read_text()
 bad=[r for r in read('records.json') if not(r['variant']=='commit0-method' and r['parallel']==8 and r['repetition']==0)]
 try:reduce(bad)
 except AssertionError:pass
 else:raise AssertionError('missing cell admitted')
 print('PASS readonly exact30-process matrix/JSON/CSV and missing-cell rejection')
else:
 (E/'summary.json').write_text(json.dumps(result,indent=2)+'\n');(E/'processes.csv').write_text(buf.getvalue())
 for c in result['cells']:print(c['parallel'],c['variant'],'wall',round(c['batch_ms_median'],1),'CPU',round(c['cpu_ms_median'],1),'Fork',round(c['fork_ms_p50_median'],2),'Close',round(c['close_ms_p50_median'],2),'COUNT',c['count_ms_pooled'],'UPDATE',c['update_ms_pooled'])
 for c in result['contrasts']:print(json.dumps({k:v for k,v in c.items() if k!='pairs'}))
 print('SLOW SQL',json.dumps(result['slow_sql']))
