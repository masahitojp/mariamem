from pathlib import Path
import json,statistics,csv,io,sys,copy
E=Path(__file__).resolve().parent
read=lambda n:json.loads((E/n).read_text())
def q(v,p):
 v=sorted(v);i=(len(v)-1)*p;a=int(i);return v[a]+(v[min(a+1,len(v)-1)]-v[a])*(i-a)
def reduce(records):
 inputs=read('inputs.json');ordinary=[r for r in records if r['repetition']>=0 and not r['negative'] and not r['warmup'] and not r['preflight']];assert len(ordinary)==20;rows=[];cells=[];pairs=[]
 for p in [4,8]:
  arms={}
  for label in ['load-off','both-off']:
   rr=sorted([r for r in ordinary if r['variant']==label and r['parallel']==p],key=lambda r:r['repetition']);assert len(rr)==5 and {r['repetition'] for r in rr}==set(range(5));rs=[]
   for r in rr:
    d=read(r['report']);m=read(r['memory']);assert r['binary_sha256']==inputs['binary_sha256'] and r['returncode']==0 and d['success'] and d['cleanup_complete'] and d['root_closed_before_forks'] and d['route']=='pipe' and d['parallel']==p;assert len(d['samples'])==48 and {s['index'] for s in d['samples']}==set(range(48)) and all(s['oracle'] and s['cleanup_complete'] and not s.get('config') for s in d['samples']) and not d.get('config');assert m['peak_active_children']==p
    v={'parallel':p,'variant':label,'round':r['repetition'],'batch_ms':d['batch_ms'],'cpu_ms':d['cpu_user_ms']+d['cpu_system_ms'],'peak_rss_mib':m['sampled_peak_rss_bytes']/2**20,'sql_over100ms':sum(s['sql_ms']>100 for s in d['samples']),'sql_over500ms':sum(s['sql_ms']>500 for s in d['samples']),'count_over100ms':sum(s['count_ms']>100 for s in d['samples']),'count_over500ms':sum(s['count_ms']>500 for s in d['samples'])}
    for metric in ['fork_ms','sql_ms','count_ms','update_ms','check_ms','cleanup_ms','retire_ms','wait_ms','close_ms']:
     vv=[s[metric] for s in d['samples']];v[metric+'_p50']=statistics.median(vv);v[metric+'_p95']=q(vv,.95);v[metric+'_max']=max(vv)
    rows.append(v);rs.append(v)
   arms[label]=rs;pooled=[s for r in rr for s in read(r['report'])['samples']];cells.append({'parallel':p,'variant':label,'process_values':rs,**{k+'_median':statistics.median(v[k] for v in rs) for k in rs[0] if k not in ['parallel','variant','round']},'sql_over100ms_count':sum(s['sql_ms']>100 for s in pooled),'sql_over500ms_count':sum(s['sql_ms']>500 for s in pooled),'pooled_sql_p50_ms':statistics.median(s['sql_ms'] for s in pooled),'pooled_sql_p95_ms':q([s['sql_ms'] for s in pooled],.95),'pooled_sql_max_ms':max(s['sql_ms'] for s in pooled)})
  for c in cells:
   if c['parallel']==p:
    pooled=[sample for r in ordinary if r['parallel']==p and r['variant']==c['variant'] for sample in read(r['report'])['samples']]
    for metric in ['count_ms','update_ms','check_ms']:
     vv=[x[metric] for x in pooled];c[metric+'_pooled_p50']=statistics.median(vv);c[metric+'_pooled_p95']=q(vv,.95);c[metric+'_pooled_max']=max(vv);c[metric+'_over100ms_count']=sum(x>100 for x in vv);c[metric+'_over500ms_count']=sum(x>500 for x in vv)
  ps=[]
  for a,b in zip(arms['load-off'],arms['both-off']):ps.append({'round':a['round'],'batch_saved_percent':100*(1-b['batch_ms']/a['batch_ms']),'cpu_saved_percent':100*(1-b['cpu_ms']/a['cpu_ms']),'fork_saved_ms':a['fork_ms_p50']-b['fork_ms_p50'],'fork_saved_percent':100*(1-b['fork_ms_p50']/a['fork_ms_p50']),'rss_added_mib':b['peak_rss_mib']-a['peak_rss_mib'],'close_saved_percent':100*(1-b['close_ms_p50']/a['close_ms_p50']),'cleanup_saved_percent':100*(1-b['cleanup_ms_p50']/a['cleanup_ms_p50'])})
  pairs.append({'parallel':p,'pairs':ps,**{k+'_median':statistics.median(v[k] for v in ps) for k in ps[0] if k!='round'}})
 gates={}
 for p in [4,8]:
  a=next(c for c in cells if c['parallel']==p and c['variant']=='load-off');b=next(c for c in cells if c['parallel']==p and c['variant']=='both-off');pair=next(v for v in pairs if v['parallel']==p);gates[str(p)]={'no_new_sql_tail':b['sql_over100ms_count']<=a['sql_over100ms_count'],'fork_cpu_batch_guard':all(pair[k]>=-5 for k in ['fork_saved_percent_median','cpu_saved_percent_median','batch_saved_percent_median']),'material_benefit':any(pair[k+'_median']>=5 and sum(v[k]>0 for v in pair['pairs'])>=4 for k in ['batch_saved_percent','close_saved_percent'])}
 recommendation='BOUNDED_CANDIDATE_REVIEW' if all(all(v.values()) for v in gates.values()) else 'STOP_INCONCLUSIVE_OR_TRADEOFF'
 return {'cells':cells,'paired':pairs,'gates':gates,'recommendation':recommendation,'both_off_has_residual_sql_tail':any(c['sql_over100ms_count']>0 for c in cells if c['variant']=='both-off'),'both_off_has_residual_count_tail':any(c['count_ms_over100ms_count']>0 for c in cells if c['variant']=='both-off'),'interpretation':'Load OFF fixed, dump ON/OFF translated-Go experiment; client query spans are not internal queue measurements or proof of permanent Issue68 resolution.'},rows
assert read('complete.json')['result']=='PASS' and read('preflight.json')['result']=='PASS';result,rows=reduce(read('records.json'));buf=io.StringIO();writer=csv.DictWriter(buf,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
if '--check' in sys.argv:
 assert result==read('summary.json') and buf.getvalue()==(E/'processes.csv').read_text();bad=[r for r in read('records.json') if not(r['variant']=='both-off' and r['parallel']==8 and r['repetition']==0)]
 try:reduce(bad)
 except AssertionError:pass
 else:raise AssertionError('missing cell admitted')
 print('PASS readonly exact20-process matrix/JSON/CSV and missing-cell rejection')
else:
 (E/'summary.json').write_text(json.dumps(result,indent=2)+'\n');(E/'processes.csv').write_text(buf.getvalue())
 for c in result['cells']:print(c['parallel'],c['variant'],'wall',round(c['batch_ms_median'],1),'CPU',round(c['cpu_ms_median'],1),'RSS',round(c['peak_rss_mib_median'],1),'Fork',round(c['fork_ms_p50_median'],2),'SQL >100/500',c['sql_over100ms_count'],c['sql_over500ms_count'],'SQL p95/max',round(c['pooled_sql_p95_ms'],2),round(c['pooled_sql_max_ms'],2))
 print(json.dumps({'paired':result['paired'],'gates':result['gates'],'recommendation':result['recommendation'],'both_off_has_residual_count_tail':result['both_off_has_residual_count_tail']},indent=2))
 for c in result['cells']:print('COUNT',c['parallel'],c['variant'],c['count_ms_over100ms_count'],c['count_ms_over500ms_count'],round(c['count_ms_pooled_p50'],2),round(c['count_ms_pooled_p95'],2),round(c['count_ms_pooled_max'],2))
