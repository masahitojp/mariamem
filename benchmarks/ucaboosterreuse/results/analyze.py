"""Read-only reduction; timings only from the ten predeclared primary processes."""
import argparse,copy,hashlib,json,statistics
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('results',type=Path);p.add_argument('--check',action='store_true');a=p.parse_args();d=a.results
r=json.loads((d/'measurements.json').read_text());inputs=json.loads((d/'inputs.json').read_text());ref=json.loads((d/'native-reference.json').read_text())
NAMES={f'round{i}-{label}' for i in range(5) for label in ['baseline','candidate']}
def validate(name,j):
 assert name in NAMES and j['result']=='PASS' and j['exit_code']==0 and len(j['children'])==4
 assert not j['cleanup_errors'] and not j['scratch_remaining']
 assert j['cleanup']=={'refs':0,'process_exit':0,'reaped':True,'root_exists':False}
 assert j['binary_sha256']==inputs['binaries'][j['label']]['sha256']
 assert j['probe_sha256']==inputs['measurement_tools']['probe.py'] and j['runner_sha256']==inputs['measurement_tools']['run_compare.py']
 assert [h['children'] for h in j['held']]==[0,1,2,4]
 for c in j['children']:
  assert c['oracle'] and c['fork_wall_ns']>0 and c['fork_cpu_ns']>0
  for mode in ['ascii','mixed']:assert c['sql'][mode]['result']==ref['perf_expected'][mode]
def summarize(records):
 assert set(records)==NAMES
 result={}
 for label in ['baseline','candidate']:
  proc=[]
  for i in range(5):
   n=f'round{i}-{label}';j=records[n];validate(n,j);med=statistics.median
   v={'fork_wall_ms':med(c['fork_wall_ns']/1e6 for c in j['children']),'fork_cpu_ms':med(c['fork_cpu_ns']/1e6 for c in j['children']),'process_wall_ms':j['controller_process_wall_ns']/1e6,'prepare_ms':j['prepare_wall_ns']/1e6}
   for mode in ['ascii','mixed']:
    v[mode+'_query_wall_ms']=med(c['sql'][mode]['wall_ns']/20/1e6 for c in j['children']);v[mode+'_query_host_cpu_ms']=med(c['sql'][mode]['host_cpu_ns']/20/1e6 for c in j['children'])
   base=j['held'][0]['rss_bytes']
   for h in j['held']:
    k=h['children'];v[f'held{k}_rss_mib']=h['rss_bytes']/2**20;v[f'held{k}_delta_rss_mib']=(h['rss_bytes']-base)/2**20
   proc.append(v)
  result[label]={'process_values':proc,'median':{k:med(v[k] for v in proc) for k in proc[0]}}
 result['paired_fork_wall_change_percent']=[(result['candidate']['process_values'][i]['fork_wall_ms']/result['baseline']['process_values'][i]['fork_wall_ms']-1)*100 for i in range(5)]
 return result
summary=summarize(r)
for kind in ['sql_result','cleanup','binary']:
 b=copy.deepcopy(r);j=b['round0-candidate']
 if kind=='sql_result':j['children'][0]['sql']['mixed']['result']='wrong'
 if kind=='cleanup':j['cleanup']['root_exists']=True
 if kind=='binary':j['binary_sha256']='0'*64
 try:summarize(b)
 except AssertionError:pass
 else:raise AssertionError('mutation accepted '+kind)
if a.check:
 assert summary==json.loads((d/'summary.json').read_text())
 for name,sha in json.loads((d/'SHA256SUMS.json').read_text()).items():assert hashlib.sha256((d/name).read_bytes()).hexdigest()==sha,name
 print('PASS readonly summary, ten primary process oracles, hashes, three rejection controls')
else:print(json.dumps(summary,indent=2))
