"""Reduce existing-init-hook observations; no build/temp dependency in check mode."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import statistics

PAIRS=[('common_before_components','embedded_begin','embedded_options_complete'),('before_plugins','embedded_options_complete','plugins_begin'),('plugins_total','plugins_begin','plugins_complete'),('after_plugins','plugins_complete','embedded_complete'),('embedded_total','embedded_begin','embedded_complete'),('myisam_cache','myisam_key_cache_begin','myisam_key_cache_complete'),('innodb_runtime','innodb_runtime_begin','innodb_start_complete'),('buffer_pool_create','buffer_pool_begin','buffer_pool_complete'),('innodb_open_recovery','innodb_memory_background_complete','innodb_open_recovery_complete')]

def unpack(c):
    r=copy.deepcopy(c['runs']);columns=c['initialization_event_columns']
    for run in r.values():
      for child in run['children']:
        d=child.get('guest',{}).get('initialization')
        if d is not None:d['events']=[dict(zip(columns,e)) for e in d['events']]
    return r

def inspect(r,negative=False):
    assert r['exit_code']==(1 if negative else 0)
    assert r['result']==('FAIL' if negative else 'PASS')
    assert not r['scratch_remaining']
    assert all(r['cleanup'][k]==0 for k in ('active_mappings','active_rw_bytes','active_reserved_bytes','release_failures'))
    if negative:assert 'seed oracle' in r['error'] and len(r['children'])==1
    else:assert len(r['children'])==4 and all(c['oracle'] for c in r['children'])
    out=[]
    for child in r['children']:
      g={x['name']:x['offset_ns'] for x in child['guest']['events']}
      v={'fork_wall_ms':child['fork_wall_ns']/1e6,'fork_cpu_ms':child['fork_cpu_ns']/1e6,'server_init_ms':(g['server_init_complete']-g['server_init_begin'])/1e6}
      if r['init_diagnostics']:
        d=child['guest']['initialization'];assert d['dropped_records']==0
        e={x['name']:x for x in d['events'] if not x['name'].startswith('plugin.')}
        assert len(e)==len([x for x in d['events'] if not x['name'].startswith('plugin.')])
        for k,a,b in PAIRS:
          assert e[b]['offset_ns']>=e[a]['offset_ns'];v[k+'_ms']=(e[b]['offset_ns']-e[a]['offset_ns'])/1e6
        stacks={};plugins={}
        for x in d['events']:
          n=x['name']
          if not n.startswith('plugin.'):continue
          name,bound=n[7:].rsplit('.',1)
          if bound=='begin':stacks.setdefault(name,[]).append(x['offset_ns'])
          elif bound=='end':
            begin=stacks[name].pop();assert x['offset_ns']>=begin
            plugins[name]=plugins.get(name,0)+(x['offset_ns']-begin)/1e6
          else:raise AssertionError('failed plugin '+name)
        assert not any(stacks.values())
        for k,t in plugins.items():v['plugin_'+k+'_ms']=t
        a,b=e['embedded_begin'],e['embedded_options_complete']
        v.update({'early_wrapped_read_bytes':b['read_bytes']-a['read_bytes'],'early_wrapped_write_bytes':b['write_bytes']-a['write_bytes'],'early_pthread_creates':b['pthread_creates']-a['pthread_creates'],'early_requested_allocation_bytes':b['wrapped_alloc_requested_bytes']-a['wrapped_alloc_requested_bytes']})
        assert all(x['process_cpu_ns'] is None and x['thread_cpu_ns'] is None for x in d['events'])
      else:assert 'initialization' not in child['guest']
      out.append(v)
    return {k:statistics.median(v[k] for v in out) for k in out[0]}

def summarize(c):
    r=unpack(c);assert len(r)==10
    all_runs={n:inspect(v,n=='negative-init') for n,v in r.items()}
    summary={}
    for mode in ('control','init'):
      cells=[all_runs[f'round{i}-{mode}'] for i in range(3)]
      summary[mode]={k:{'median':statistics.median(v[k] for v in cells),'process_medians':[v[k] for v in cells]} for k in cells[0]}
    summary['paired_fork_wall_percent']=[(all_runs[f'round{i}-init']['fork_wall_ms']/all_runs[f'round{i}-control']['fork_wall_ms']-1)*100 for i in range(3)]
    summary['method']='4 child medians per fresh process;3 process medians per mode. Nested intervals are not additive across medians. Guest CPU counters unavailable, not zero.'
    return summary

def mutations(c):
    run=unpack(c)['round0-init']
    for kind in ('missing_marker','dropped','hidden_failure'):
      b=copy.deepcopy(run)
      if kind=='missing_marker':
        d=b['children'][0]['guest']['initialization'];d['events']=[x for x in d['events'] if x['name']!='embedded_options_complete']
      elif kind=='dropped':b['children'][0]['guest']['initialization']['dropped_records']=1
      else:b['children'][0]['oracle']=False
      try:inspect(b)
      except (AssertionError,KeyError):pass
      else:raise AssertionError('accepted '+kind)

def main():
    p=argparse.ArgumentParser();p.add_argument('--collect',type=Path);p.add_argument('--results',type=Path,required=True);p.add_argument('--check',action='store_true');a=p.parse_args();d=a.results
    if a.collect:
      assert not a.check;d.mkdir(exist_ok=True,parents=True)
      names=['pilot-init','negative-init','warmup-control','warmup-init']+[f'round{i}-{mode}' for i in range(3) for mode in ('control','init')]
      raw={name:json.loads((a.collect/(name+'.json')).read_text()) for name in names}
      columns=list(raw['pilot-init']['children'][0]['guest']['initialization']['events'][0]);count=0
      for r in raw.values():
        for child in r['children']:
          diag=child.get('guest',{}).get('initialization')
          if diag is not None:
            encoded=[]
            for e in diag['events']:
              assert list(e)==columns;encoded.append([e[k] for k in columns]);count+=1
            diag['events']=encoded
      c={'schema':1,'initialization_event_columns':columns,'encoded_initialization_events':count,'runs':raw,'raw_sha256':{name+'.json':hashlib.sha256((a.collect/(name+'.json')).read_bytes()).hexdigest() for name in names}}
      for name,r in unpack(c).items():assert r==json.loads((a.collect/(name+'.json')).read_text())
      (d/'compact.json').write_text(json.dumps(c,separators=(',',':'))+'\n')
    c=json.loads((d/'compact.json').read_text());mutations(c);s=summarize(c)
    if a.check:
      assert json.loads((d/'summary.json').read_text())==s
      for name,sha in json.loads((d/'SHA256SUMS.json').read_text()).items():assert hashlib.sha256((d/name).read_bytes()).hexdigest()==sha,name
      print('PASS: read-only reduction,10 process oracles, zero drops, paired plugin boundaries, hashes,3 rejection controls')
    else:(d/'summary.json').write_text(json.dumps(s,indent=2)+'\n')
if __name__=='__main__':main()
