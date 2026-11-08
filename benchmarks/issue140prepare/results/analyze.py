import json,pathlib,re,argparse,hashlib,copy
p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args();root=pathlib.Path(__file__).resolve().parent;o=json.loads((root/'observations.json').read_text());assert len(o)==9
required=[('p6','Fn16624'),('p8','Fn16787'),('p3','Fn18164')]
def dbblocks(text,db):
 out=[]
 for block in text.split('\n\n'):
  labels=next((json.loads(l[len('# labels: '):]) for l in block.splitlines() if l.startswith('# labels: ')),{})
  if labels.get('db_id')==db:out.append(block)
 return out
def in_scope(c,text):
 return not c['truncated'] and not c.get('error') and c['call_enter_us']<=c['snapshot_begin_us']<=c['snapshot_end_us']<=c['call_return_us'] and bool(dbblocks(text,c['db_id']))
def foreground(c,text):
 return [b for b in dbblocks(text,c['db_id']) if all('/'+part+'.'+fn in b for part,fn in required)]
summary={'result':'NATURAL_PREPARE_CAPTURED; immediate page-read-completion path differs from old UPDATE writer acquisition, common root cause UNVERIFIED','natural_runs':[],'captures':[],'control':{},'negative_mutations':[]}
expected={'begin':1,'prepare':3,'order_insert':40,'item_insert':100,'stock_update':100,'commit':1,'statement_close':3,'rollback_cleanup':1}
for r in o:
 assert len(r['loaders'])==21 and all({k:len(v) for k,v in l['durations_us'].items()}==expected for l in r['loaders'])
 meta=r['trace']['meta'];assert meta['read_cases']=='50' and meta['write_cases']=='20' and meta['test_exit']=='0' and meta['active_mappings_after']=='0';assert meta['innodb_buffer_pool_size']==meta['innodb_buffer_pool_size_max']==str(r['pool_mib']*2**20)
 longs=[{'lane':l['lane'],'phase':v['phase'],'duration_ms':v['duration_us']/1000} for l in r['loaders'] for v in l['operations_ge50ms'] or [] if v['duration_us']>=100000]
 if not r['control']:summary['natural_runs'].append({'name':r['name'],'block':r['block'],'pool_mib':r['pool_mib'],'watcher':r['watcher'],'suite_ms':r['trace']['elapsed_ms'],'long_calls':longs,'captures':len(r['captures'])})
 assert len(r['captures'])<=1
 if not r['watcher']:assert not r['captures']
 for c in r['captures']:
  text=(root/r['name']/c['profile_file']).read_text();assert hashlib.sha256(text.encode()).hexdigest()==c['profile_sha256'];assert len(text.encode())==c['bytes'];assert in_scope(c,text) and c['usable']
  if r['control']:
   assert c['phase']=='positive_control' and any('/p7.Fn5853' in b for b in dbblocks(text,c['db_id']))
   summary['control']={'call_ms':(c['call_return_us']-c['call_enter_us'])/1000,'snapshot_ms':(c['snapshot_end_us']-c['snapshot_begin_us'])/1000,'matching_db_blocks':len(dbblocks(text,c['db_id'])),'profile_bytes':c['bytes']};continue
  assert c['phase']=='prepare' and c['prepare_ordinal']==1
  loader=next(l for l in r['loaders'] if l['db_id']==c['db_id'] and l['lane']==c['lane']);assert loader['start_us']<=c['call_enter_us']<=c['call_return_us']<=loader['start_us']+loader['total_us']+3
  assert abs((c['call_return_us']-c['call_enter_us'])-loader['durations_us']['prepare'][0])<1000
  fg=foreground(c,text);assert len(fg)==1
  chain=re.findall(r'generatedgo/code/(p\d+)\.(Fn\d+)',fg[0]);assert 'base.go:1946' in fg[0]
  bg=[b for b in dbblocks(text,c['db_id']) if '/p8.Fn16787' in b and '/p4.Fn17217' in b and '/p3.Fn18164' not in b];assert len(bg)==1
  summary['captures'].append({'run':r['name'],'pool_mib':r['pool_mib'],'db_id':c['db_id'],'lane':c['lane'],'sql':'INSERT INTO orders(user_id, status) VALUES (?, ?) RETURNING id','caller_ms':(c['call_return_us']-c['call_enter_us'])/1000,'snapshot_after_entry_ms':(c['snapshot_begin_us']-c['call_enter_us'])/1000,'snapshot_ms':(c['snapshot_end_us']-c['snapshot_begin_us'])/1000,'foreground_function_chain':chain,'background_function_chain':re.findall(r'generatedgo/code/(p\d+)\.(Fn\d+)',bg[0]),'profile_sha256':c['profile_sha256'],'profile_bytes':c['bytes']})
  for kind in ('wrong_db','outside_window','truncated','missing_read_wait'):
   m=copy.deepcopy(c);data=text
   if kind=='wrong_db':m['db_id']='different-instance'
   elif kind=='outside_window':m['call_return_us']=m['snapshot_begin_us']-1
   elif kind=='truncated':m['truncated']=True
   else:data=data.replace('/p8.Fn16787','/p8.FnNOTMATCHED')
   assert not (in_scope(m,data) and foreground(m,data)),kind
  summary['negative_mutations'].append({'run':r['name'],'rejected':['wrong_db','outside_window','truncated','missing_read_wait']})
assert len(summary['natural_runs'])==8 and len(summary['captures'])==2
assert summary['captures'][0]['foreground_function_chain']==summary['captures'][1]['foreground_function_chain']
summary['same_foreground_chain_across_pool_sizes']=True
text=json.dumps(summary,indent=2)+'\n'
if a.check:assert (root/'summary.json').read_text()==text
else:(root/'summary.json').write_text(text)
print(text)
