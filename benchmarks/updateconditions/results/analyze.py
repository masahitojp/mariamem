from pathlib import Path
import json,csv,io,sys,copy,math,statistics
E=Path(__file__).resolve().parent
read=lambda n:json.loads((E/n).read_text())
def percentile(v,q):
 a=sorted(v);p=(len(a)-1)*q;lo=math.floor(p);hi=math.ceil(p);return a[lo]+(a[hi]-a[lo])*(p-lo)
def stats(v):
 assert v and all(math.isfinite(x) for x in v)
 return {'n':len(v),'p50':percentile(v,.5),'p95':percentile(v,.95),'max':max(v),'over100':sum(x>100 for x in v),'over500':sum(x>500 for x in v)}
def reduce(records):
 expected=['effective','wrong-seed','pair0-delay0','pair0-delay500','pair1-delay500','pair1-delay0','pair2-delay0','pair2-delay500']
 assert [r['name'] for r in records]==expected
 rows=[];samples=[];byarm={0:[],500:[]}
 i=read('inputs.json')
 assert not read('host.json')['observer_variables_present']
 for r in records:
  d=read(r['report']);ss=d['samples'];delay=r['delay_ms']
  assert d['cleanup_complete'] and d['root_closed_before_forks'] and d['route']=='pipe' and d['parallel']==r['parallel'] and d['update_delay_ms']==delay and d['gomaxprocs']==8
  assert r['binary_sha256']==i['binary_sha256']
  if r['negative']:
   assert r['name']=='wrong-seed' and r['exit_code']!=0 and not d['success'] and 'pristine oracle' in d['error']
   assert all(not x['oracle1'] and not x['oracle2'] and x['delay_actual_ms']==0 and x['first_fork_age_ms']==0 and x['second_fork_age_ms']==0 for x in ss)
   continue
  assert r['exit_code']==0 and d['success'] and len(ss)==r['count'] and {x['index'] for x in ss}==set(range(r['count']))
  for x in ss:
   assert x['oracle'] and x['oracle1'] and x['oracle2'] and x['cleanup_complete']
   assert all(math.isfinite(x[k]) and x[k]>=0 for k in ['update_ms','update2_ms','check_ms','check2_ms','delay_actual_ms','first_fork_age_ms','second_fork_age_ms'])
   assert x['delay_actual_ms']>=delay-.01 and x['first_fork_age_ms']>=x['delay_actual_ms']
   assert x['second_fork_age_ms']>=x['first_fork_age_ms']+x['update_ms']+x['check_ms']-.01
   assert abs(x['offset_ms']+x['fork_ms']+x['first_fork_age_ms']-x['update1_start_offset_ms'])<.01
   assert abs(x['offset_ms']+x['fork_ms']+x['second_fork_age_ms']-x['update2_start_offset_ms'])<.01
   assert sum(x[k] for k in ['count_ms','delay_actual_ms','update_ms','check_ms','update2_ms','check2_ms'])<=x['sql_ms']+.01
  if r['preflight']:
   assert r['name']=='effective' and len(ss)==8
   for c in [d['config']]+[x['config'] for x in ss]:
    assert c['innodb_buffer_pool_load_at_startup']=='OFF' and c['innodb_buffer_pool_dump_at_shutdown']=='OFF' and c['innodb_flush_log_at_trx_commit']=='1' and c['innodb_flush_method']=='O_DIRECT'
   continue
  assert r['pair'] in [0,1,2] and r['parallel']==8 and r['count']==48 and delay in [0,500]
  assert not d.get('config') and all(not x.get('config') for x in ss)
  first=stats([x['update_ms'] for x in ss]);second=stats([x['update2_ms'] for x in ss])
  row={'process':r['name'],'pair':r['pair'],'delay_ms':delay,'batch_ms':d['batch_ms'],'count':48}
  for label,st in [('first',first),('second',second)]:
   for k in ['p50','p95','max','over100','over500']:row[label+'_'+k]=st[k]
  row['within_child_second_minus_first_p50']=statistics.median(x['update2_ms']-x['update_ms'] for x in ss)
  rows.append(row)
  for x in ss:
   first_at=x['update1_start_offset_ms'];second_at=x['update2_start_offset_ms']
   v=dict(process=r['name'],pair=r['pair'],delay_ms=delay,**x)
   v['other_forks_at_update1']=sum(y['offset_ms']<=first_at<y['offset_ms']+y['fork_ms'] for y in ss if y['index']!=x['index'])
   v['other_forks_at_update2']=sum(y['offset_ms']<=second_at<y['offset_ms']+y['fork_ms'] for y in ss if y['index']!=x['index'])
   samples.append(v);byarm[delay].append(v)
 arms={};tails=[]
 for delay,ss in byarm.items():
  assert len(ss)==144
  arms[str(delay)]={name:stats([x[key] for x in ss]) for name,key in [('first','update_ms'),('second','update2_ms'),('actual_delay','delay_actual_ms'),('first_fork_age','first_fork_age_ms'),('second_fork_age','second_fork_age_ms')]}
  arms[str(delay)]['within_child_second_minus_first']=stats([x['update2_ms']-x['update_ms'] for x in ss])
  arms[str(delay)]['second_faster_children']=sum(x['update2_ms']<x['update_ms'] for x in ss)
  tails += [x for x in ss if x['update_ms']>100 or x['update2_ms']>100]
 pairs=[]
 for pair in range(3):
  a=next(r for r in rows if r['pair']==pair and r['delay_ms']==0);b=next(r for r in rows if r['pair']==pair and r['delay_ms']==500)
  pairs.append({'pair':pair,'first_p50_delayed_minus_immediate_ms':b['first_p50']-a['first_p50'],'second_p50_delayed_minus_immediate_ms':b['second_p50']-a['second_p50'],'first_tail_counts':[a['first_over100'],b['first_over100']],'second_tail_counts':[a['second_over100'],b['second_over100']]})
 result='NOT_REPRODUCED' if not tails else 'TAILS_IN_SECOND_UPDATE' if any(x['update2_ms']>100 for x in tails) else 'FIRST_UPDATE_TAILS_ONLY'
 return {'result':result,'primary_children':288,'primary_updates':576,'controls':2,'processes':rows,'arms':arms,'pairs':pairs,'slow_children':tails,'all_samples':samples,'limits':'Condition intervention; pause changes DB age and overlap. Second write changes data/undo/cache state and elapsed time. No population/cause/fix or speedup conclusion. All raw samples retained.'},rows
s,rows=reduce(read('records.json'));b=io.StringIO();w=csv.DictWriter(b,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
if '--check' in sys.argv:
 assert s==read('summary.json') and b.getvalue()==(E/'processes.csv').read_text()
 try:reduce(read('records.json')[:-1])
 except AssertionError:pass
 else:raise AssertionError('missing cell accepted')
 original_read=read
 for mode in ['missing_second_oracle','short_idle','wrong_age']:
  def bad_read(n):
   d=original_read(n)
   if n=='pair0-delay500.json':
    d=copy.deepcopy(d)
    if mode=='missing_second_oracle':d['samples'][0]['oracle2']=False
    elif mode=='short_idle':d['samples'][0]['delay_actual_ms']=0
    else:d['samples'][0]['first_fork_age_ms']+=10
   return d
  read=bad_read
  try:reduce(original_read('records.json'))
  except AssertionError:pass
  else:raise AssertionError(mode+' accepted')
  finally:read=original_read
 print('PASS readonly8-process/6-cell two-update/idle/age/SQL/cleanup reduction; missing-cell/second-oracle/short-idle/wrong-age rejected')
else:
 (E/'summary.json').write_text(json.dumps(s,indent=2)+'\n');(E/'processes.csv').write_text(b.getvalue());print(json.dumps({k:v for k,v in s.items() if k not in ['all_samples','slow_children']},indent=2))
