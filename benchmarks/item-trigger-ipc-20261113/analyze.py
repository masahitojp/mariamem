from pathlib import Path
import json,statistics,collections,csv,sys,base64,gzip
r=Path(__file__).resolve().parent
def load_event(path):
 if path.exists():return json.loads(path.read_text())
 return json.loads(gzip.decompress(base64.b64decode(path.with_suffix(path.suffix+'.gz.b64').read_bytes())))
FIELDS=['total','pre','inbound','service','outbound','post','transport','outside_service']
def process(record):
 d=load_event(r/(record['name']+'-events.json'));ledgers={l['label']:l for l in d['ledgers']};assert len(ledgers)==len(d['ledgers'])
 bylabel=collections.defaultdict(list);samples={};raw=[]
 for c in d['clients']:
  if c['Stage']=='sample':samples[c['Label']]=c['End']-c['Start']
  if c['Stage']!='item':continue
  l=ledgers[c['Label']];assert l['joined'] and not l['exit_error'] and not l['parse_error']
  matches=[v for v in l['requests'].values() if v['HostWriteStart']>=c['Start'] and v['HostReadEnd']<=c['End'] and v['HostReadEnd']>0]
  assert len(matches)==1,(record['name'],c,len(matches))
  q=matches[0];assert q['Op']==5 and q['Command']==23,q
  times=[c['Start'],q['HostWriteStart'],q['GuestReadEnd'],q['GuestWriteStart'],q['HostReadEnd'],c['End']]
  assert all(b>=a for a,b in zip(times,times[1:])),(record['name'],c,q)
  dif=[b-a for a,b in zip(times,times[1:])];total=c['End']-c['Start'];assert sum(dif)==total
  values=dict(zip(FIELDS,[total,*dif,dif[1]+dif[3],total-dif[2]]));bylabel[c['Label']].append(values);raw.append({'name':record['name'],'label':c['Label'],'index':c['Index'],'request_id':q['ID'],**values})
 expected=16 if record['kind']=='isolated' else 21
 assert len(bylabel)==expected and len(samples)==expected,(record['name'],len(bylabel),len(samples))
 for label,items in bylabel.items():assert len(items)==100,label
 # Additive means per100 INSERTs; no sum of overlapping children as wall.
 summary={k:statistics.mean(sum(x[k] for x in a)/1e6 for a in bylabel.values()) for k in FIELDS}
 summary['sample_ms']=statistics.mean(v/1e6 for v in samples.values());summary['loads']=len(bylabel);summary['items']=len(raw)
 assert abs(summary['pre']+summary['inbound']+summary['service']+summary['outbound']+summary['post']-summary['total'])<1e-6
 return summary,raw
if __name__=='__main__':
 rows=json.loads((r/'runs.json').read_text());allout=[];rawall=[]
 for row in rows:
  assert row['returncode']==0
  if row['observe']:
   summary,raw=process(row);allout.append({**row,'breakdown_ms_per100':summary});rawall+=raw
 summary={}
 for p in [1,8]:
  for arm in ['full','incremental','none']:
   a=[x for x in allout if x['name'].startswith('primary-') and x['parallel']==p and x['arm']==arm];assert len(a)==3
   summary[f'p{p}-{arm}']={k:statistics.median(x['breakdown_ms_per100'][k] for x in a) for k in FIELDS+['sample_ms']}
 if '--check' in sys.argv:
  assert json.loads((r/'summary.json').read_text())['groups']==summary
 else:(r/'summary.json').write_text(json.dumps({'groups':summary,'processes':allout},indent=2))
 if '--check' not in sys.argv:
  with (r/'items.csv').open('w') as f:
   w=csv.DictWriter(f,fieldnames=list(rawall[0]));w.writeheader();w.writerows(rawall)
 print(json.dumps(summary,indent=2));print('PASS: request binding, causal timestamps, additive per-item intervals, 100 INSERTs/load, joined exits')
