from pathlib import Path
import json,statistics,csv,io,sys,copy
E=Path(__file__).resolve().parent;read=lambda n:json.loads((E/n).read_text())
def reduce(records):
 natural=[r for r in records if r['name'].startswith('natural-')];assert 1<=len(natural)<=3;assert {r['name'] for r in natural}=={f'natural-{i}' for i in range(len(natural))};rows=[]
 for r in natural:
  d=read(r['report']);assert d['success'] and d['cleanup_complete'] and d['root_closed_before_forks'] and d['route']=='pipe' and d['parallel']==8 and not d.get('config');assert len(d['samples'])==48 and {s['index'] for s in d['samples']}==set(range(48)) and all(s['oracle'] and s['cleanup_complete'] for s in d['samples'])
  v={'name':r['name'],'children':48,'captures':len(r['captures'])}
  for k in ['count_ms','update_ms','check_ms']:
   vals=[s[k] for s in d['samples']];v[k+'_p50']=statistics.median(vals);v[k+'_max']=max(vals);v[k+'_over100']=sum(x>100 for x in vals)
  rows.append(v)
 pilot=next(r for r in records if r['artificial']);assert pilot['name']=='artificial-client' and len(pilot['captures'])==1;meta=read(pilot['captures'][0]['meta']);assert meta['artificial'] and meta['labels_bound'] and not meta['truncated'];assert 100<=meta['snapshot_begin_ms']<meta['snapshot_end_ms']<200 and meta['exec_return_ms']>=200
 neg=next(r for r in records if r['negative']);d=read(neg['report']);assert not d['success'] and d['cleanup_complete'] and 'pristine oracle' in d['error'];assert not neg['captures']
 complete=read('complete.json');assert complete['result']=='NOT_REPRODUCED' and len(natural)==3;assert sum(v['update_ms_over100'] for v in rows)==0 and all(not r['captures'] for r in natural)
 return {'result':'NOT_REPRODUCED','original366ms_phase':'UNDETERMINED','natural_processes':len(natural),'natural_children':48*len(natural),'natural_update_over100ms':0,'natural_snapshots':0,'rows':rows,'artificial_control':{'timer_and_correct_child_guest_labels':'PASS','snapshot_begin_ms':meta['snapshot_begin_ms'],'snapshot_end_ms':meta['snapshot_end_ms'],'wrapper_return_ms':meta['exec_return_ms'],'scope':'Artificial200ms client delay before Exec; confirms observer/labels, not an engine wait or actual SQL in progress.'},'metadata_limit':'Original metadata field whole_profile_inside_exec refers to wrapper observation window including the artificial hold. No SQL-call entry timestamp is recorded. No natural capture was used for a phase claim. Future reuse for engine phase classification must distinguish Exec entry from wrapper entry.','conclusion':'Bounded observation completed without reproducing the slow UPDATE. Original cause, commit/flush attribution and relationship to old COUNT queue stalls remain unknown. Zero cases does not establish resolution or a frequency.'},rows
result,rows=reduce(read('records.json'));buf=io.StringIO();wr=csv.DictWriter(buf,fieldnames=list(rows[0]),lineterminator='\n');wr.writeheader();wr.writerows(rows)
if '--check' in sys.argv:
 assert result==read('summary.json') and buf.getvalue()==(E/'processes.csv').read_text()
 bad=[r for r in read('records.json') if r['name']!='natural-1']
 try:reduce(bad)
 except AssertionError:pass
 else:raise AssertionError('missing natural process admitted')
 print('PASS readonly natural matrix/control/negative/summary/CSV and missing-process rejection')
else:(E/'summary.json').write_text(json.dumps(result,indent=2)+'\n');(E/'processes.csv').write_text(buf.getvalue());print(json.dumps(result,indent=2))
