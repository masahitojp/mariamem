from pathlib import Path
import json,sys,statistics
D=Path(sys.argv[1]);n=sys.argv[2];obs=json.loads((D/(n+'-events.json')).read_text());clients=json.loads((D/(n+'-clients.json')).read_text());rows=[]
for inst in obs:
 label=inst['Label']
 if label not in clients:continue
 req={}
 for e in inst['Events']:
  r=req.setdefault(e['ID'],{});assert e['Name'] not in r,('duplicate',label,e);r[e['Name']]=e['NS']
 reqs=sorted([r for r in req.values()if 'stage3'in r],key=lambda r:r['call_begin']);assert len(reqs)==len(clients[label])==100
 for r,(a,z)in zip(reqs,clients[label]):
  for k in ['call_begin','queue_begin','queue_acquired','write_begin','write_end','guest_frame','stage0','stage3','stage4','stage5','stage6','host_frame','host_decode','notify_begin','call_end']:assert k in r,(label,k)
  assert len([k for k in r if k.startswith('slot:')])==1
  seq=['call_begin','queue_begin','queue_acquired','write_begin','guest_frame','stage0','stage3','stage4','stage5','host_frame','host_decode','notify_begin','call_end'];ts=[a]+[r[k]for k in seq]+[z];assert all(x<=y for x,y in zip(ts,ts[1:])),(label,ts)
  row={'label':label,'serial':inst['Serial']}
  for k,x,y in [('client_setup',a,r['call_begin']),('submit',r['call_begin'],r['write_begin']),('queue',r['queue_begin'],r['queue_acquired']),('write_inclusive',r['write_begin'],r['write_end']),('input_delivery',r['write_begin'],r['guest_frame']),('dispatch',r['guest_frame'],r['stage0']),('pre_sql',r['stage0'],r['stage3']),('sql',r['stage3'],r['stage4']),('result',r['stage4'],r['stage5']),('response_delivery',r['stage5'],r['host_frame']),('decode',r['host_frame'],r['host_decode']),('return',r['host_decode'],z),('reply_inclusive',r['stage5'],r['stage6']),('exec',a,z)]:row[k]=(y-x)/1e6
  rows.append(row)
assert len(rows)==800
summary={k:sum(r[k]for r in rows)/8 for k in rows[0]if k not in ['label','serial']}
summary['exclusive_sum']=sum(summary[k]for k in ['client_setup','submit','input_delivery','dispatch','pre_sql','sql','result','response_delivery','decode','return']);assert abs(summary['exclusive_sum']-summary['exec'])<1e-5
(D/(n+'-reduced.json')).write_text(json.dumps(summary,indent=2));print('MATCHED',n,len(rows),flush=True)
