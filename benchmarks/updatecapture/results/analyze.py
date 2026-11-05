from pathlib import Path
import json,statistics,csv,io,sys,re,hashlib
E=Path(__file__).resolve().parent;read=lambda n:json.loads((E/n).read_text())
def inspect_capture(c):
 m=read(c['meta']);text=(E/c['text']).read_text();inside=m['exec_enter_ms']>0 and m['snapshot_begin_ms']>=m['exec_enter_ms'] and m['snapshot_end_ms']>=m['snapshot_begin_ms'] and m['snapshot_end_ms']<=m['exec_return_ms'];assert m['whole_profile_inside_exec']==m['snapshot_inside_actual_exec']==inside;assert m['usable']==(inside and m['labels_bound'] and not m['truncated']);assert len(text.encode())==m['bytes'] and m['bytes']<=2<<20
 groups=[]
 for group in text.split('\n\n'):
  labels={}
  for line in group.splitlines():
   if line.startswith('# labels: '):
    try:labels=json.loads(line[len('# labels: '):])
    except ValueError:pass
  if labels.get('child')==str(m['child']) and 'internal/generatedgo/code/p' in group:groups.append(group)
 query=[g for g in groups if re.search(r'\.Fn5853(?:\+|\s)',g)]
 return {**m,'profile_sha256':hashlib.sha256(text.encode()).hexdigest(),'matching_guest_groups':len(groups),'current_mysql_real_query_groups':len(query),'query_atomic_wait_groups':sum('AtomicWait' in g or 'Futex_wait' in g for g in query),'matching_generated_functions':sorted(set(re.findall(r'\.Fn(\d+)(?:\+|\s)', '\n\n'.join(groups))),key=int),'meta_file':c['meta'],'text_file':c['text']}
def reduce(records):
 assert len(records)==6 and {r['name'] for r in records}=={'effective','sql-sleep-control','wrong-seed','natural-0','natural-1','natural-2'}
 rows=[];captures=[]
 for r in records:
  d=read(r['report']);assert d['cleanup_complete'] and d['root_closed_before_forks'] and d['route']=='pipe' and d['parallel']==r['parallel'] and d['gomaxprocs']==8
  if r['negative']:assert r['exit_code']!=0 and not d['success'] and 'pristine oracle' in d['error'] and not r['captures'];continue
  assert r['exit_code']==0 and d['success'] and len(d['samples'])==r['count'] and {x['index'] for x in d['samples']}==set(range(r['count'])) and all(x['oracle'] and x['cleanup_complete'] for x in d['samples'])
  assert len(r['captures'])<=1
  for c in r['captures']:
   m=inspect_capture(c);assert m['artificial']==r['artificial'];captures.append(dict(process=r['name'],**m))
  if r['artificial']:
   assert len(r['captures'])==1 and r['captures'][0]['usable'] and d['samples'][0]['update_ms']>=200
   continue
  if r['preflight']:
   for cfg in [d['config']]+[x['config'] for x in d['samples']]:assert cfg['innodb_buffer_pool_load_at_startup']=='OFF' and cfg['innodb_buffer_pool_dump_at_shutdown']=='OFF' and cfg['innodb_flush_log_at_trx_commit']=='1' and cfg['innodb_flush_method']=='O_DIRECT'
   continue
  expected={'natural-0':8,'natural-1':4,'natural-2':8};assert r['parallel']==expected[r['name']] and r['count']==48 and not d.get('config') and all(not x.get('config') for x in d['samples'])
  v={'name':r['name'],'parallel':r['parallel'],'children':48,'captures':len(r['captures']),'usable_captures':sum(c['usable'] for c in r['captures'])}
  for k in ['count_ms','update_ms','check_ms']:
   vals=[s[k] for s in d['samples']];v[k+'_p50']=statistics.median(vals);v[k+'_max']=max(vals);v[k+'_over100']=sum(x>100 for x in vals);v[k+'_over500']=sum(x>500 for x in vals)
  rows.append(v)
 assert len(rows)==3
 natural=[c for c in captures if c['process'].startswith('natural-')];slow=sum(x['update_ms_over100'] for x in rows);valid=sum(c['usable'] for c in natural);expected='NATURAL_UPDATE_CAPTURED' if valid else 'SLOW_UPDATE_WITHOUT_USABLE_CAPTURE' if slow else 'NOT_REPRODUCED';assert read('complete.json')['result']==expected
 return {'result':expected,'natural_processes':3,'natural_children':144,'update_over100ms':slow,'update_over500ms':sum(r['update_ms_over500'] for r in rows),'rows':rows,'captures':captures,'natural_usable_captures':valid,'natural_query_entry_captures':sum(c['usable'] and c['current_mysql_real_query_groups']>0 for c in natural),'scope':'Diagnostic source-bound processes, not a performance comparison. Natural absence is not cure/frequency proof. Artificial SQL SLEEP validates observer only; unmapped generated functions are not assigned C names.'},rows
summary,rows=reduce(read('records.json'));buf=io.StringIO();wr=csv.DictWriter(buf,fieldnames=list(rows[0]),lineterminator='\n');wr.writeheader();wr.writerows(rows)
if '--check' in sys.argv:
 assert summary==read('summary.json') and buf.getvalue()==(E/'processes.csv').read_text()
 try:reduce(read('records.json')[:-1])
 except AssertionError:pass
 else:raise AssertionError('missing process admitted')
 print('PASS readonly exact6-process capture/window/summary/CSV and missing-process rejection')
else:(E/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(E/'processes.csv').write_text(buf.getvalue());print(json.dumps(summary,indent=2))
