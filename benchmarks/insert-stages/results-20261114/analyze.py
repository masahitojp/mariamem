from pathlib import Path
import json,statistics,csv
E=Path(__file__).resolve().parent;med=statistics.median;out=[];dbrows=[]
for row in json.loads((E/'records.json').read_text()):
 n=row['name'];trace=json.loads((E/(n+'-trace.json')).read_text());sp=[s['end_ms']-s['start_ms'] for s in trace['spans'] if s['name']=='raw_insert'];assert len(sp)==8
 obs=json.loads((E/(n+'-stages.json')).read_text());row.update(raw_p50_ms=med(sp),raw_mean_ms=statistics.mean(sp),raw_max_ms=max(sp))
 if row['arm']:
  assert len(obs)==8
  for m in obs:
   rs=m['records'];assert len(rs)==100
   sums={k:0 for k in ['input','bind','old_parameter_cleanup','execute','result','reply','fd_write','worker']}
   for r in rs:
    t=r['T'];assert r['Counts']==[1]*7 and r['Writes']==1
    assert all(a<=b for a,b in zip(t,t[1:]))
    for k,i,j in [('input',0,1),('bind',1,2),('old_parameter_cleanup',2,3),('execute',3,4),('result',4,5),('reply',5,6),('worker',0,6)]:sums[k]+=(t[j]-t[i])/1e6
    sums['fd_write']+=r['WriteNS']/1e6
   assert abs(sums['worker']-sum(sums[k]for k in ['input','bind','old_parameter_cleanup','execute','result','reply']))<1e-6
   dbrows.append(dict(name=n,parallel=row['parallel'],phase=row['phase'],module=m['module'],**sums))
  mine=[r for r in dbrows if r['name']==n]
  for k in sums:row[k+'_mean_ms']=statistics.mean(r[k]for r in mine);row[k+'_p50_ms']=med(r[k]for r in mine)
  row['outer_minus_worker_ms']=row['raw_mean_ms']-row['worker_mean_ms']
 out.append(row)
summary={}
for p in [1,8]:
 runs=[r for r in out if r['parallel']==p and r['phase']=='primary'];b=[r for r in runs if r['arm']==0];c=[r for r in runs if r['arm']==1]
 summary[str(p)]={'off_raw_p50_ms':med(r['raw_p50_ms']for r in b),'on_raw_p50_ms':med(r['raw_p50_ms']for r in c),'raw_p50_paired_pct':[100*(c[i]['raw_p50_ms']/b[i]['raw_p50_ms']-1)for i in range(3)],'on_raw_mean_ms':med(r['raw_mean_ms']for r in c)}
 for k in ['input','bind','old_parameter_cleanup','execute','result','reply','fd_write','worker']:summary[str(p)][k+'_mean_ms']=med(r[k+'_mean_ms']for r in c)
 summary[str(p)]['outer_minus_worker_ms']=med(r['outer_minus_worker_ms']for r in c)
 summary[str(p)]['execute_share_worker_pct']=[r['execute_mean_ms']/r['worker_mean_ms']*100 for r in c]
 for k in ['wall_ms','cpu_ms']:summary[str(p)][k+'_paired_pct']=[100*(c[i][k]/b[i][k]-1)for i in range(3)]
(E/'summary.json').write_text(json.dumps(summary,indent=2));(E/'analyzed-runs.json').write_text(json.dumps(out,indent=2))
with(E/'db-stages.csv').open('w')as f:
 w=csv.DictWriter(f,fieldnames=list(dbrows[0]),lineterminator="\n");w.writeheader();w.writerows(dbrows)
print(json.dumps(summary,indent=2))
pooled={}
for p in [1,8]:
 rs=[r for r in out if r['phase']=='primary' and r['arm']==1 and r['parallel']==p]
 d={k:statistics.mean(r[k]for r in rs)for k in rs[0]if k.endswith('_mean_ms')or k=='outer_minus_worker_ms'}
 d['input_total_ms']=sum(d[k]for k in ['input_mean_ms','bind_mean_ms','old_parameter_cleanup_mean_ms'])
 d['execute_share_worker_pct']=d['execute_mean_ms']/d['worker_mean_ms']*100;pooled[p]=d
(E/'pooled-means.json').write_text(json.dumps(pooled,indent=2))
