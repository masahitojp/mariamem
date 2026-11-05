from pathlib import Path
import json,sys,csv,io,statistics,hashlib,copy
E=Path(__file__).resolve().parent;read=lambda n:json.loads((E/n).read_text())
def reduce(records):
 assert len(records)==6 and {r['name'] for r in records}=={'effective','sql-sleep-control','wrong-seed','natural-0','natural-1','natural-2'}
 rows=[];waits=[];tails=[];captures=[]
 for r in records:
  d=read(r['report']);assert d['cleanup_complete'] and d['root_closed_before_forks'] and d['parallel']==r['parallel'] and d['route']=='pipe';assert len(r['captures'])<=1
  if r['negative']:assert r['exit_code']!=0 and not d['success'] and 'pristine oracle' in d['error'] and not r['captures'];continue
  assert r['exit_code']==0 and d['success'] and len(d['samples'])==r['count'] and all(x['oracle'] and x['cleanup_complete'] for x in d['samples'])
  assert len(r['notify_reports'])==r['count'];bychild={}
  for filename in r['notify_reports']:
   tr=read(filename);child=tr['child'];assert child not in bychild and not tr['truncated'] and len(tr['events'])<=8192;bychild[child]=tr
   events=tr['events'];queries=[v for v in events if v['kind']=='query_begin'];assert len(queries)==1;qid=queries[0]['query'];ends=[v for v in events if v['kind']=='query_end' and v['query']==qid];assert len(ends)==1 and ends[0]['ns']>=queries[0]['ns']
   registrations=[v for v in events if v['kind']=='wait_registered']
   for reg in registrations:
    wid=reg['wait'];ee=[v for v in events if v.get('wait')==wid];returns=[v for v in ee if v['kind']=='wait_return'];assert len(returns)==1;ret=returns[0];assert ret['ns']>=reg['ns'] and ret['ea']==reg['ea'] and ret['thread']==reg['thread'] and ret['query']==qid
    bef=[v for v in ee if v['kind']=='signal_before'];aft=[v for v in ee if v['kind']=='signal_after'];res=[v for v in ee if v['kind']=='wait_resume'];assert len(bef)==len(aft)<=1
    row={'process':r['name'],'natural':r['name'].startswith('natural-'),'child':child,'query':qid,'wait':wid,'ea':reg['ea'],'waiter_thread':reg['thread'],'page':reg.get('page',0),'space':reg.get('space',0),'rseg':reg.get('rseg',0),'mutex':reg.get('mutex',0),'timeout_ns':reg.get('timeout',0),'return_rc':ret.get('rc',0),'registered_ns':reg['ns'],'return_ns':ret['ns'],'registered_to_return_ms':(ret['ns']-reg['ns'])/1e6,'signaled':bool(bef),'trace_file':filename}
    if bef:
     b,a=bef[0],aft[0];assert b['ns']<=a['ns'] and b['ns']>=reg['ns'] and len(res)==1 and res[0]['ns']>=b['ns'] and ret['ns']>=res[0]['ns'];nid=b['notify'];assert nid==a['notify'] and b['ea']==a['ea']==reg['ea'] and b['query']==a['query']==qid and b['thread']==a['thread']==reg['thread'];attempt=[v for v in events if v['kind']=='notify_attempt' and v.get('notify')==nid];nr=[v for v in events if v['kind']=='notify_return' and v.get('notify')==nid];assert len(attempt)==len(nr)==1;attempt,nr=attempt[0],nr[0];assert attempt['ea']==nr['ea']==reg['ea'] and attempt['ns']<=b['ns'] and nr['ns']>=a['ns'] and nr['rc']>=1
     row.update(notify=nid,notifier_thread=attempt['thread'],signal_before_ns=b['ns'],signal_after_ns=a['ns'],resume_ns=res[0]['ns'],notify_attempt_ns=attempt['ns'],notify_return_ns=nr['ns'],pre_signal_lower_ms=(b['ns']-reg['ns'])/1e6,pre_signal_upper_ms=(a['ns']-reg['ns'])/1e6,signal_to_resume_lower_ms=max(0,(res[0]['ns']-a['ns'])/1e6),signal_to_resume_upper_ms=(res[0]['ns']-b['ns'])/1e6,notify_attempt_to_signal_upper_ms=(a['ns']-attempt['ns'])/1e6,notifier_callers=nr.get('callers',[]))
    else:assert not res and ret.get('rc')==2
    waits.append(row)
  assert set(bychild)=={x['index'] for x in d['samples']}
  for c in r['captures']:
   m=read(c['meta']);inside=m['exec_enter_ms']>0 and m['snapshot_begin_ms']>=m['exec_enter_ms'] and m['snapshot_end_ms']<=m['exec_return_ms'];assert m['whole_profile_inside_exec']==m['snapshot_inside_actual_exec']==inside and m['usable']==(inside and m['labels_bound'] and not m['truncated']);assert len((E/c['text']).read_bytes())==m['bytes'];captures.append(dict(process=r['name'],**m,text_file=c['text']))
  if r['artificial']:assert d['samples'][0]['update_ms']>=200 and len(r['captures'])==1 and r['captures'][0]['usable'];continue
  if r['preflight']:
   for cfg in [d['config']]+[x['config'] for x in d['samples']]:assert cfg['innodb_buffer_pool_load_at_startup']=='OFF' and cfg['innodb_buffer_pool_dump_at_shutdown']=='OFF' and cfg['innodb_flush_log_at_trx_commit']=='1' and cfg['innodb_flush_method']=='O_DIRECT'
   continue
  assert not d.get('config') and r['parallel']=={'natural-0':8,'natural-1':4,'natural-2':8}[r['name']] and r['count']==48
  row={'name':r['name'],'parallel':r['parallel'],'children':48,'update_p50_ms':statistics.median(x['update_ms'] for x in d['samples']),'update_max_ms':max(x['update_ms'] for x in d['samples']),'update_over100':sum(x['update_ms']>100 for x in d['samples']),'captures':len(r['captures'])};rows.append(row)
  for x in d['samples']:
   if x['update_ms']>100:tails.append(dict(process=r['name'],**x))
 assert len(rows)==3;naturalwaits=[w for w in waits if w['natural']];tailkeys={(v['process'],v['index']) for v in tails};long=[w for w in naturalwaits if w['registered_to_return_ms']>100];matched=[w for w in long if w['rseg'] and w['signaled'] and (w['process'],w['child']) in tailkeys];classification='MATCHED_NATURAL_PAGE_WAIT' if matched else 'NATURAL_SLOW_QUERY_WITHOUT_MATCHED_LONG_PAGE_WAIT' if tails else 'NOT_REPRODUCED'
 for w in long:
  if not w['signaled']:
   w['delay_classification']='UNSIGNALED_OR_TIMEOUT';continue
  span=(w['resume_ns']-w['registered_ns'])/1e6
  w['delay_classification']='BEFORE_NOTIFY' if w['pre_signal_lower_ms']>=0.8*span else 'AFTER_NOTIFY' if w['signal_to_resume_lower_ms']>=0.8*span else 'MIXED_OR_UNRESOLVED'
  w['register_to_resume_ms']=span
 signaled=[w for w in naturalwaits if w['signaled']];pagewaits=[w for w in signaled if w['rseg']]
 stats={'signaled_natural_waits':len(signaled),'page_scoped_signaled_waits':len(pagewaits)}
 for label,ww in [('all',signaled),('page_scoped',pagewaits)]:
  for key in ['registered_to_return_ms','pre_signal_upper_ms','signal_to_resume_upper_ms','notify_attempt_to_signal_upper_ms']:
   vals=[w[key] for w in ww];stats[label+'_'+key]={'p50':statistics.median(vals) if vals else None,'max':max(vals) if vals else None}
 return {'result':classification,'normal_wait_stats':stats,'natural_processes':3,'natural_children':144,'processes':rows,'slow_updates':tails,'natural_waits':len(naturalwaits),'long_natural_waits':long,'matched_long_page_waits':matched,'all_waits':waits,'captures':captures,'scope':'Instrumented diagnostic; page path is current source correspondence. A matching notifier path is not necessarily the original lock owner. Close bounds bracket actual channel close; scheduling and trace costs included. No performance/fix/adoption claim.'},rows
summary,rows=reduce(read('records.json'));buf=io.StringIO();wr=csv.DictWriter(buf,fieldnames=list(rows[0]),lineterminator='\n');wr.writeheader();wr.writerows(rows)
if '--check' in sys.argv:
 assert summary==read('summary.json') and buf.getvalue()==(E/'processes.csv').read_text()
 try:reduce(read('records.json')[:-1])
 except AssertionError:pass
 else:raise AssertionError('missing process accepted')
 real_read=read
 target=next((w for w in summary['all_waits'] if w['signaled']),None)
 assert target is not None, 'SQL control must supply a signaled wait for mutation checks'
 for mutation in ['wrong_ea','missing_notify_return']:
  def bad_read(n):
   d=real_read(n)
   if n==target['trace_file']:
    d=copy.deepcopy(d)
    if mutation=='wrong_ea':
     for event in d['events']:
      if event['kind']=='signal_after' and event.get('wait')==target['wait']:event['ea']+=4
    else:d['events']=[e for e in d['events'] if not(e['kind']=='notify_return' and e.get('notify')==target['notify'])]
   return d
  read=bad_read
  try:reduce(real_read('records.json'))
  except AssertionError:pass
  else:raise AssertionError('invalid binding admitted: '+mutation)
  finally:read=real_read
 print('PASS readonly exact6-process SQL/namespace/wait-ID/channel-notify/window/JSON/CSV; missing-process/wrong-EA/missing-notify rejected')
else:
 (E/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(E/'processes.csv').write_text(buf.getvalue());print(json.dumps({k:v for k,v in summary.items() if k not in ['all_waits','captures']},indent=2))
