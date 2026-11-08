import argparse, json, pathlib, statistics, hashlib, csv, io
p=argparse.ArgumentParser(); p.add_argument('--check',action='store_true'); a=p.parse_args(); root=pathlib.Path(__file__).resolve().parent
median=statistics.median
def p95(v): return sorted(v)[-(-95*len(v)//100)-1]
observations=json.loads((root/'observations.json').read_text())
serial=observations['serial']; hold=observations['hold']
assert all(r['success'] and r['mapping_stats']['active_mappings']==0 for r in serial+hold)
assert all(r['settings']=={'innodb_buffer_pool_size':16777216,'innodb_buffer_pool_size_max':16777216} for r in serial+hold)
samples=[dict(repeat=i,**v) for i,r in enumerate(serial) for v in r['samples']]
assert len(samples)==240
out={'scope':'Single-Mac current-main 16MiB baseline, not an 8MiB comparison or product acceptance. No exclusions.','processes':10,'primary_serial_children':240,'warmup_serial_children':5,'series':{},'rss':[]}
for key in ('fork_ms','fork_cpu_ms','first_sql_ms','disconnect_ms','close_ms'):
    v=[r[key] for r in samples]
    out['series'][key]={'pooled_p50':median(v),'pooled_p95':p95(v),'max':max(v),'over_100ms':sum(x>100 for x in v),'per_process_p50':[median([v[key] for v in r['samples']]) for r in serial]}
for i,r in enumerate(hold):
    points=r['rss_points']; b=points['0']['rss_bytes']; one=(points['1']['rss_bytes']-b)/2**20; four=(points['4']['rss_bytes']-b)/2**20
    out['rss'].append({'repeat':i,'baseline_mib':b/2**20,'one_child_increment_mib':one,'four_child_increment_mib':four,'four_child_per_child_mib':four/4})
out['rss_medians']={k:median([v[k] for v in out['rss']]) for k in ('baseline_mib','one_child_increment_mib','four_child_increment_mib','four_child_per_child_mib')}
text=json.dumps(out,indent=2)+'\n'
buf=io.StringIO(); w=csv.DictWriter(buf,fieldnames=list(samples[0])); w.writeheader(); w.writerows(samples)
for name,data in [('summary.json',text)]:
    if a.check: assert (root/name).read_text()==data,name
    else: (root/name).write_text(data)
print(text)
