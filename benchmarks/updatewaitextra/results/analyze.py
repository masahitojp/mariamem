from pathlib import Path
import json,statistics,csv,io,sys
E=Path(__file__).resolve().parent;read=lambda n:json.loads((E/n).read_text())
def reduce(records):
 assert len(records)==3 and {r['name'] for r in records}=={'extra-0','extra-1','extra-2'};rows=[];captures=[]
 for r in sorted(records,key=lambda r:r['name']):
  d=read(r['report']);assert r['exit_code']==0 and not r['artificial'] and not r['negative'] and not r['preflight'];assert d['success'] and d['cleanup_complete'] and d['root_closed_before_forks'] and d['route']=='pipe' and d['parallel']==8 and not d.get('config');assert len(d['samples'])==48 and {s['index'] for s in d['samples']}==set(range(48)) and all(s['oracle'] and s['cleanup_complete'] for s in d['samples'])
  v={'name':r['name'],'children':48,'captures':len(r['captures']),'usable_captures':sum(c['usable'] for c in r['captures'])}
  for k in ['count_ms','update_ms','check_ms']:
   vals=[s[k] for s in d['samples']];v[k+'_p50']=statistics.median(vals);v[k+'_max']=max(vals);v[k+'_over100']=sum(x>100 for x in vals);v[k+'_over500']=sum(x>500 for x in vals)
  assert len(r['captures'])<=1
  for c in r['captures']:
   m=read(c['meta']);assert not m['artificial'];inside=m['exec_enter_ms']>0 and m['snapshot_begin_ms']>=m['exec_enter_ms'] and m['snapshot_end_ms']<=m['exec_return_ms'];assert m['whole_profile_inside_exec']==m['snapshot_inside_actual_exec']==inside;assert m['usable']==(inside and m['labels_bound'] and not m['truncated']);captures.append(dict(process=r['name'],**m))
  rows.append(v)
 slow=sum(x['update_ms_over100'] for x in rows);valid=sum(c['usable'] for c in captures);expected='NATURAL_UPDATE_CAPTURED' if valid else 'SLOW_UPDATE_WITHOUT_USABLE_CAPTURE' if slow else 'NOT_REPRODUCED';assert read('complete.json')['result']==expected
 return {'result':expected,'natural_processes':3,'natural_children':144,'update_over100ms':slow,'update_over500ms':sum(r['update_ms_over500'] for r in rows),'rows':rows,'captures':captures,'usable_captures':valid,'scope':'Three newly authorized diagnostic processes, separately source-bound from previous three. No frequency/performance or resolution claim.'},rows
summary,rows=reduce(read('records.json'));buf=io.StringIO();wr=csv.DictWriter(buf,fieldnames=list(rows[0]),lineterminator='\n');wr.writeheader();wr.writerows(rows)
if '--check' in sys.argv:
 assert summary==read('summary.json') and buf.getvalue()==(E/'processes.csv').read_text()
 try:reduce(read('records.json')[:-1])
 except AssertionError:pass
 else:raise AssertionError('missing process admitted')
 print('PASS readonly exact3-process capture/window/summary/CSV and missing-process rejection')
else:(E/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(E/'processes.csv').write_text(buf.getvalue());print(json.dumps(summary,indent=2))
