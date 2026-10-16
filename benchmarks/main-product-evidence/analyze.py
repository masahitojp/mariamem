"""Summarize every finite-campaign cell without discarding slow observations."""
from pathlib import Path
import csv,json,statistics,sys
w=Path(sys.argv[1]); evidence=w/'evidence'; out=evidence/'analysis';out.mkdir(exist_ok=False)
rows=[]; pilots=[]; phases=[]
for path in sorted((evidence/'matrix').glob('*.json')):
 if path.name=='inputs.json':continue
 parts=path.stem.split('-');pilot=parts[0]=='pilot'
 if pilot:parts=parts[1:]
 label,language,case,trial,mode=parts
 d=json.loads(path.read_text());row=dict(file=path.name,label=label,language=language,case=case,trial=int(trial),mode=mode)
 if language=='go':
  m=d['resources']['after_go']['linear_memory_virtual'];expected=d['forks']+(1 if mode=='fork' else 0)
  assert m['active_mappings']==m['active_reserved_bytes']==m['active_rw_bytes']==m['release_failures']==0,path
  assert m['creates']==m['releases']==expected,path
  o=d['go_resource_observation'];row.update(wall_seconds=d['suite_product_seconds'],observed_wall_seconds=d['suite_seconds'],cpu_seconds=d['suite_cpu_seconds'],peak_rss_mib=o['process_peak_rss_bytes']/1024**2,peak_go_heap_mib=o['sampled_peak_go_heap_objects_bytes']/1024**2,cumulative_alloc_mib=o['cumulative_alloc_bytes']/1024**2,after_heap_bytes=d['resources']['after_go']['heap_alloc_bytes'],mapping_creates=m['creates'],mapping_releases=m['releases'],fd_delta=d['fds_after']-d['fds_before'])
  starts=[]
  for op in d['operations']:
   phases.append(dict(file=path.name,label=label,language=language,case=case,trial=int(trial),mode=mode,phase=op['name'],seconds=op['seconds'],pilot=pilot))
   if op['name']=='prepare_start' or op['name'].startswith(('fresh_ready_','fork_ready_')):starts.append(op['seconds'])
  row['starts_seconds']=starts;row['snapshot_seconds']=next((v['seconds'] for v in d['operations'] if v['name']=='snapshot'),None)
 else:
  assert d['completed'] and len(d['samples'])==d['count'],path
  assert all(v['server_version'].startswith('12.3.3') for v in d['samples']),path
  row.update(wall_seconds=d['suite_wall_seconds'],cpu_seconds=d['runner_and_reaped_host_cpu_seconds'],starts_seconds=[v['ready_seconds'] for v in d['samples']],prepare_snapshot_seconds=d.get('prepare_snapshot_seconds'))
  for sample in d['samples']:
   for key in ['ready_seconds','prepare_seconds','sql_seconds','cleanup_seconds','resource_observation_seconds']:
    phases.append(dict(file=path.name,label=label,language=language,case=case,trial=int(trial),mode=mode,phase=str(sample['index'])+'/'+key,seconds=sample[key],pilot=pilot))
 (pilots if pilot else rows).append(row)
assert len(rows)==80 and len(pilots)==8
summary=[]
for language in ['go','python']:
 for case in ['light','fixture','parallel','large']:
  for mode in ['fresh','fork']:
   entry=dict(language=language,case=case,mode=mode)
   for label in ['baseline','candidate']:
    cell=[r for r in rows if (r['label'],r['language'],r['case'],r['mode'])==(label,language,case,mode)]
    assert len(cell)==(1 if case=='large' else 3)
    values=[r['wall_seconds'] for r in cell]
    starts=[v for r in cell for v in r['starts_seconds']]
    entry[label]={'n':len(cell),'wall_seconds':values,'median_seconds':statistics.median(values),'min_seconds':min(values),'max_seconds':max(values),'cpu_seconds':[r['cpu_seconds'] for r in cell],'starts_seconds':starts,'starts_ge_900ms':sum(v>=.9 for v in starts)}
    if language=='go':
     for metric in ['peak_rss_mib','peak_go_heap_mib','cumulative_alloc_mib','after_heap_bytes','fd_delta']:
      entry[label][metric]=[r[metric] for r in cell]
     entry[label]['snapshot_seconds']=[r['snapshot_seconds'] for r in cell if r['snapshot_seconds'] is not None]
   entry['change_percent']=100*(entry['candidate']['median_seconds']/entry['baseline']['median_seconds']-1)
   summary.append(entry)
repeats={}
for campaign,expect in [('sharedhost',54),('small-repeat',120)]:
 allrows=[json.loads(p.read_text()) for pattern in ['plain-*.json','resource-*.json'] for p in (evidence/campaign).glob(pattern)]
 assert len(allrows)==expect
 for r in allrows:assert r['result']=='PASS'
 for resources in [False,True]:
  for label in ['baseline','candidate']:
   items=[r for r in allrows if r['scale']=='small' and r['resources_enabled']==resources and r['label']==label]
   repeats[f'{campaign}/{resources}/{label}']={'n':len(items),'whole_ms':[r['whole_ms'] for r in items],'whole_ge_1000ms':sum(r['whole_ms']>=1000 for r in items),'prepare_start_ge_900ms':sum(r['times_ms']['prepare/start']>=900 for r in items),'all_starts':sum(sum(k.endswith('/start') for k in r['times_ms']) for r in items),'all_starts_ge_900ms':sum(sum(v>=900 for k,v in r['times_ms'].items() if k.endswith('/start')) for r in items),'largest_phases':[{'whole_ms':r['whole_ms'],'phases':sorted(r['times_ms'].items(),key=lambda p:p[1],reverse=True)[:3]} for r in items if r['whole_ms']>=1000]}
extra=[]
receipt=json.loads((evidence/'large-repeat/receipt.json').read_text())
assert receipt['completed'] and len(receipt['cells'])==12 and all(c['returncode']==0 for c in receipt['cells'])
for cell in receipt['cells']:
 path=evidence/'large-repeat'/(cell['name']+'.json');d=json.loads(path.read_text());parts=cell['name'].split('-')
 m=d['resources']['after_go']['linear_memory_virtual'];expected=4+(parts[-1]=='fork')
 assert m['active_mappings']==m['active_reserved_bytes']==m['active_rw_bytes']==m['release_failures']==0,path
 assert m['creates']==m['releases']==expected,path
 o=d['go_resource_observation'];row=dict(file='large-repeat/'+path.name,label=parts[0],mode=parts[-1],trial=int(parts[-2]),wall_seconds=d['suite_product_seconds'],cpu_seconds=d['suite_cpu_seconds'],peak_rss_mib=o['process_peak_rss_bytes']/1024**2,cumulative_alloc_mib=o['cumulative_alloc_bytes']/1024**2,after_heap_bytes=d['resources']['after_go']['heap_alloc_bytes'],mapping_creates=m['creates'],mapping_releases=m['releases'],snapshot_seconds=next((v['seconds'] for v in d['operations'] if v['name']=='snapshot'),None))
 extra.append(row)
 for op in d['operations']:
  phases.append(dict(file=row['file'],label=row['label'],language='go',case='large-repeat',trial=row['trial'],mode=row['mode'],phase=op['name'],seconds=op['seconds'],pilot=False))
extra_summary={}
for mode in ['fresh','fork']:
 entry={}
 for label in ['baseline','candidate']:
  items=[r for r in extra if r['label']==label and r['mode']==mode];assert len(items)==3
  entry[label]={metric:[r[metric] for r in items] for metric in ['wall_seconds','cpu_seconds','peak_rss_mib','cumulative_alloc_mib','snapshot_seconds']}
  entry[label]['median_seconds']=statistics.median(entry[label]['wall_seconds'])
 entry['change_percent']=100*(entry['candidate']['median_seconds']/entry['baseline']['median_seconds']-1)
 extra_summary[mode]=entry
all_large={}
for mode in ['fresh','fork']:
 entry={}
 for label in ['baseline','candidate']:
  items=[r for r in rows if (r['label'],r['language'],r['case'],r['mode'])==(label,'go','large',mode)]+[r for r in extra if r['label']==label and r['mode']==mode]
  assert len(items)==4
  entry[label]={'files':[r['file'] for r in items]}
  for metric in ['wall_seconds','cpu_seconds','peak_rss_mib','cumulative_alloc_mib']:
   entry[label][metric]=[r[metric] for r in items]
   entry[label]['median_'+metric]=statistics.median(entry[label][metric])
 entry['change_percent']=100*(entry['candidate']['median_wall_seconds']/entry['baseline']['median_wall_seconds']-1)
 all_large[mode]=entry
report={'matrix':summary,'small_case_repeats':repeats,'sharedhost':json.loads((evidence/'sharedhost/summary.json').read_text()),'large_followup':extra_summary,'invariants':{'matrix_oracles':'80 measured + 8 pilots completed; Go memory mapping creates/releases balanced; Python completed/version counts checked; SQL assertions stop each process','go_mapping_total_measured':sum(r['mapping_creates'] for r in rows if r['language']=='go'),'go_mapping_total_pilots':sum(r['mapping_creates'] for r in pilots if r['language']=='go'),'go_after_heap_max_bytes':max(r['after_heap_bytes'] for r in rows if r['language']=='go'),'sharedhost_oracles':'174 processes PASS including seed/commit/rollback/sibling isolation/reaped host/scratch-empty assertions','go_followup_oracles':'12 processes PASS, unchanged SQL oracles and balanced memory mappings','go_followup_mappings':sum(r['mapping_creates'] for r in extra)},'scope':'macOS arm64 only; sharedhost regular latency and sampled RSS separately; Go product wall excludes diagnostic probes; no cross-schema pooled comparisons; 12 post-hoc adverse-case repeats kept separate from the original 262 executions'}
assert report['invariants']['go_mapping_total_measured']==180 and report['invariants']['go_mapping_total_pilots']==6
report['large_all_observations']=all_large
report['invariants']['go_after_heap_max_including_followup_bytes']=max([r['after_heap_bytes'] for r in rows if r['language']=='go']+[r['after_heap_bytes'] for r in extra])
(out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
(out/'cells.json').write_text(json.dumps(rows,indent=2)+'\n');(out/'pilots.json').write_text(json.dumps(pilots,indent=2)+'\n')
(out/'large-followup.json').write_text(json.dumps(extra,indent=2)+'\n')
with (out/'phases.csv').open('w') as f:
 writer=csv.DictWriter(f,fieldnames=list(phases[0]));writer.writeheader();writer.writerows(phases)
print('language,case,mode,baseline_seconds,candidate_seconds,change_percent')
for r in summary:print(r['language'],r['case'],r['mode'],round(r['baseline']['median_seconds'],4),round(r['candidate']['median_seconds'],4),round(r['change_percent'],1),sep=',')
for key,r in repeats.items():print(key,'n',r['n'],'whole>=1s',r['whole_ge_1000ms'],'start>=900ms',r['prepare_start_ge_900ms'])
for mode,r in extra_summary.items():print('large follow-up',mode,round(r['baseline']['median_seconds'],3),round(r['candidate']['median_seconds'],3),round(r['change_percent'],1))
assert report['invariants']['go_followup_mappings']==54
print('PASS: all 262 + 12 executions and unchanged SQL/resource invariants accounted for')
