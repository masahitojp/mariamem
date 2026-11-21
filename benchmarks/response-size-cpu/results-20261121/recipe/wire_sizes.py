"""Use observed framing overhead to target wire sizes in addition to SQL result sizes."""
from run import measure,out,itertools
sizes=[3920,8016,16208,32592,130896]
for name in ('wire-perf','wire-diag'):
    assert not (out/(name+'.csv')).exists()
for block,order in enumerate(itertools.permutations(('os','ring','os2')),1):
    for size in sizes if block%2 else reversed(sizes):
        for arm in order:measure(arm,size,block,'wire-perf')
for size in sizes:
    for arm in ('os-diag','ring-diag'):measure(arm,size,1,'wire-diag')
