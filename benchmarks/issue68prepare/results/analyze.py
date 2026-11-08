import pathlib,json,re,argparse,hashlib,copy
p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args();root=pathlib.Path(__file__).resolve().parent;o=json.loads((root/'observations.json').read_text())
def blocks(text,db):
 out=[]
 for block in text.split('\n\n'):
  labels=next((json.loads(line[len('# labels: '):]) for line in block.splitlines() if line.startswith('# labels: ')),{})
  if labels.get('db_id')==db:out.append(block)
 return out
def usable(c,text,control=False):
 b=blocks(text,c['db_id']);guest=[v for v in b if re.search(r'/internal/generatedgo/code/p\d+\.Fn\d+',v)]
 return (not c['truncated'] and not c.get('error') and c['call_enter_us']<=c['snapshot_begin_us']<=c['snapshot_end_us']<=c['call_return_us'] and bool(guest) and (not control or any('/p7.Fn5853' in v for v in guest)))
assert len(o)==5 and sum(r['control'] for r in o)==1
summary={'result':'PARTIAL: no usable natural PREPARE capture; relation to prior Issue68 mechanism remains unverified','controls':{},'natural':[],'late_control_prepare_calls':[],'no_resampling':True}
for r in o:
 assert r['trace']['meta']['read_cases']=='50' and r['trace']['meta']['write_cases']=='20' and r['trace']['meta']['active_mappings_after']=='0' and r['trace']['meta']['test_exit']=='0';assert len(r['loaders'])==21
 caps=r['captures'];assert len(caps)<=1
 for c in caps:
  text=(root/r['name']/c['profile_file']).read_text();assert hashlib.sha256(text.encode()).hexdigest()==c['profile_sha256'];assert usable(c,text,r['control'])
  assert c['usable'] and c['matching_db_blocks']==len(blocks(text,c['db_id']))
 if r['control']:
  assert len(caps)==1
  c=caps[0];text=(root/r['name']/c['profile_file']).read_text();assert c['phase']=='positive_control';bodies=json.loads((root/'prior-function-body-comparison.json').read_text());assert bodies['5853']['exact_body_equal']
  summary['controls']={'scope_ms':(c['call_return_us']-c['call_enter_us'])/1000,'profile_begin_after_enter_ms':(c['snapshot_begin_us']-c['call_enter_us'])/1000,'profile_duration_ms':(c['snapshot_end_us']-c['snapshot_begin_us'])/1000,'matching_db_blocks':c['matching_db_blocks'],'matching_guest_blocks':c['matching_guest_blocks'],'foreground_query_anchor':'current p7.Fn5853; exact body equality against prior named mysql_real_query anchor','truncated':c['truncated'],'profile_bytes':c['bytes']}
  # Boundary mutation controls operate on the real bounded profile.
  for kind in ('db','outside_window','truncated','no_guest'):
   v=copy.deepcopy(c);data=text
   if kind=='db':v['db_id']='wrong-instance'
   elif kind=='outside_window':v['call_return_us']=v['snapshot_begin_us']-1
   elif kind=='truncated':v['truncated']=True
   else:data='no guest frames'
   assert not usable(v,data,True),kind
  summary['controls']['negative_mutations_rejected']=['wrong DB','outside caller window','truncated profile','no guest frames']
  for l in r['loaders']:
   for v in l['operations_ge50ms'] or []:
    if v['phase']=='prepare' and v['duration_us']>=100000:summary['late_control_prepare_calls'].append({'lane':l['lane'],'duration_ms':v['duration_us']/1000,'profile':'not captured; reserved control slot already used'})
 else:
  calls=[v for l in r['loaders'] for v in l['durations_us']['prepare']];assert len(calls)==63
  summary['natural'].append({'name':r['name'],'pool_mib':r['pool_mib'],'suite_ms':r['trace']['elapsed_ms'],'prepare_calls':len(calls),'max_prepare_ms':max(calls)/1000,'prepare_ge100ms':sum(v>=100000 for v in calls),'captures':len(caps)})
assert len(summary['natural'])==4
text=json.dumps(summary,indent=2)+'\n'
if a.check:assert (root/'summary.json').read_text()==text
else:(root/'summary.json').write_text(text)
print(text)
