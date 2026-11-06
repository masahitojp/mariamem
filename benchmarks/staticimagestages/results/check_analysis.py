import copy, json, gzip
from pathlib import Path
from analyze import reduce
p=Path(__file__).parent
x=json.loads(gzip.decompress((p/'observations.json.gz').read_bytes()));reduce(x)
checks=[]
for name,mutate in [
 ('missing nested startup',lambda v:v[0]['report']['samples'][0]['traces'].pop('startup')),
 ('misaligned clocks',lambda v:v[0]['report']['samples'][0]['traces']['startup'].update(epoch_ns=0)),
 ('missing boundary',lambda v:v[0]['report']['samples'][0]['traces']['fork']['events'].pop()),
 ('negative partition',lambda v:v[0]['report']['samples'][0]['spans'][0].update(end_ms=-1)),
 ('duplicate child',lambda v:v[0]['report']['samples'][1].update(index=0)),
 ('missing owner',lambda v:v[0]['owner']['child_indices'].pop()),
 ('cleanup debt',lambda v:v[0]['report']['cleanup_stats'].update(active_mappings=1)),
 ('extra process',lambda v:v.append(v[0]))]:
 bad=copy.deepcopy(x);mutate(bad)
 try:reduce(bad)
 except (AssertionError,KeyError):checks.append(name)
 else:raise AssertionError('not rejected: '+name)
print('PASS:',', '.join(checks))
