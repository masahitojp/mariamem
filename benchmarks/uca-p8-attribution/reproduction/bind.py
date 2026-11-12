from pathlib import Path
import json,re,hashlib,subprocess
W=Path(__file__).resolve().parents[1];E=W/'evidence';T=W/'temp';S=W/'worktree';old='a3b2b6457147e2b8edbd31fec77ab6ec04f11b22'
parts={'Fn16624':'p6','Fn16787':'p8','Fn18164':'p3','Fn216':'p4','Fn88':'p7'}
def body(t,fn):
 m=re.search(r'^func '+fn+r'\(.*?(?=\nfunc |\Z)',t,re.M|re.S);assert m;return m.group(),t.count('\n',0,m.start())+1
record={'kind':'structural source correspondence, not a complete C symbol map','older_mapping_source_commit':old,'arms':{},'captures':[]}
excerpt=[]
for arm in ['baseline','candidate']:
 rec={}
 for fn,part in parts.items():
  path=f'internal/generatedgo/code/{part}/{part}_pure.go';text=(T/arm/path).read_text();b,line=body(text,fn)
  prev=body(subprocess.check_output(['git','show',old+':'+path],cwd=S,text=True),fn)[0]
  a=re.sub(r'(?<![A-Za-z_])\d+', 'N',b);c=re.sub(r'(?<![A-Za-z_])\d+', 'N',prev)
  rec[fn]={'path':path,'line':line,'sha256':hashlib.sha256(b.encode()).hexdigest(),'same_non_numeric_tokens_as_older_mapping':a==c}
  if fn=='Fn16624':assert 'v13 = l0 + int32(28)' in b and 'Fn216(m, v13, v15, int32(0))' in b
  if fn=='Fn16787':assert 'if l1 != 0 {' in b and b.count('Fn16624(m, l0+int32(24))')==2 and 'Fn16583(m)' in b and 'Fn16584(m)' in b
  if fn=='Fn18164':assert 'Fn16787(m, v580, v108)' in b
  if fn in ['Fn16624','Fn16787']:excerpt.append('### '+arm+' '+path+':'+str(line)+'\n\n```go\n'+b+'```\n')
 record['arms'][arm]=rec
for c in json.loads((E/'report/captures.json').read_text()):
 if c['mode']!='diagnostic':continue
 blocks=(E/'report'/c['retained_profile']).read_text().split('\n\n')
 selected=[b for b in blocks if '"db_id":"'+c['db_id']+'"' in b and '.Fn267+' in b];assert len(selected)==1
 names=re.findall(r'(p\d+\.Fn\d+)\+',selected[0]);assert names[:5]==['p7.Fn88','p4.Fn216','p6.Fn16624','p8.Fn16787','p3.Fn18164']
 record['captures'].append({'name':c['name'],'db_id':c['db_id'],'phase':c['phase'],'operation_ordinal':c['operation_ordinal'],'call_ms':(c['call_return_us']-c['call_enter_us'])/1000,'snapshot_cost_ms':(c['snapshot_end_us']-c['snapshot_begin_us'])/1000,'snapshot_offset_ms':(c['snapshot_begin_us']-c['call_enter_us'])/1000,'foreground_generated_chain':names,'host_wait':'AtomicWait/AtomicWait32At/Futex_wait','interpretation':'Buffer page get -> read completion wait -> shared-lock slow path; structural correspondence with historical Issue140, not proof of same page, task owner or entire wait history.'})
(E/'report/source-binding.json').write_text(json.dumps(record,indent=2)+'\n')
(E/'report/source-excerpts.md').write_text('# Current generated read-wait anchors\n\nNo source mutation. Numeric-token comparison is an analysis aid only, never an execution guard.\n\n'+''.join(excerpt))
print(json.dumps({k:{fn:x['same_non_numeric_tokens_as_older_mapping'] for fn,x in v.items()} for k,v in record['arms'].items()},indent=2))
