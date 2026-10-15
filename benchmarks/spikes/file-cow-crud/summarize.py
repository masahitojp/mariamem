"""Reduce a bounded campaign without treating probe timing as backend performance."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import statistics

def dist(xs):
    return {'n':len(xs),'min':min(xs),'median':statistics.median(xs),'max':max(xs)} if xs else None

def summarize(root):
    rows=[]
    for path in sorted(root.glob('*/result.json')):
        result=json.loads(path.read_text())
        if result['warmup']:continue
        assert len(result['checks'])==3, path
        for child in result['children']:
            name=child['name']
            row={'rows':result['rows'],'repeat':result['repeat'],'mode':result['mode'],'child':name,
                 'times_ms':{k.split('/')[1]:v for k,v in result['times_ms'].items() if k.startswith(name+'/')},
                 'workflow_ms':result['workflow_ms_before_validation']+result['times_ms']['baseline/close']}
            if result['mode']!='control':
                audit=json.loads((path.parent/(str(child['pid'])+'.json')).read_text())
                assert audit['role']=='fork'
                manifest=result['baseline_manifest']['entries']
                assert len(audit['nodes'])==sum(v['kind']=='file' for v in manifest.values())
                row['baseline_bytes']=sum(n['baseline_bytes'] for n in audit['nodes'])
                row['phases']=defaultdict(lambda:dict(copy_bytes=0,copy_probe_ms=0,write_bytes=0))
                row['files']=[]
                for node in audit['nodes']:
                    copies=sum(p['copy_bytes'] for p in node['phases'].values())
                    row['files'].append({'path':node['path'],'baseline_bytes':node['baseline_bytes'],
                       'copy_bytes':copies,'first_copy_phase':node.get('first_copy_phase'),
                       'first_copy_op':node.get('first_copy_op'),'phases':node['phases']})
                    for phase,s in node['phases'].items():
                        suffix=phase.split('/')[-1]
                        row['phases'][suffix]['copy_bytes']+=s['copy_bytes']
                        row['phases'][suffix]['copy_probe_ms']+=s['copy_probe_ns']/1e6
                        row['phases'][suffix]['write_bytes']+=s['write_bytes']
                row['total_copy_bytes']=sum(n['copy_bytes'] for n in row['files'])
                row['total_copy_probe_ms']=sum(p['copy_probe_ms'] for p in row['phases'].values())
            rows.append(row)
    groups=[]
    for n in sorted(set(r['rows'] for r in rows)):
        for mode in ['control','observe','copy-probe']:
            group=[r for r in rows if r['rows']==n and r['mode']==mode]
            if not group:continue
            item={'rows':n,'mode':mode,'children':len(group),
                  'times_ms':{p:dist([r['times_ms'][p] for r in group]) for p in ['startup','connect','crud','disconnect','close']},
                  'suite_ms':dist([r['workflow_ms'] for r in group if r['child']=='first'])}
            if mode!='control':
                item['baseline_bytes']=dist([r['baseline_bytes'] for r in group])
                item['total_copy_bytes']=dist([r['total_copy_bytes'] for r in group])
                item['total_copy_probe_ms']=dist([r['total_copy_probe_ms'] for r in group])
                item['phases']={p:{k:dist([r['phases'].get(p,{}).get(k,0) for r in group]) for k in ['copy_bytes','copy_probe_ms','write_bytes']} for p in ['startup','connect','crud','disconnect','close']}
            groups.append(item)
    return {'note':'Counterfactual copy volume and additive copy probe; NOT a file-CoW implementation or net speedup measurement.',
            'campaigns':len(rows)//2,'groups':groups,'children':rows}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('output',type=Path)
    args=p.parse_args();data=summarize(args.root)
    args.output.write_text(json.dumps(data,indent=2)+'\n')
    for g in data['groups']:
        print(g['rows'],g['mode'],'suite median ms',round(g['suite_ms']['median'],2),
              'copy MiB',round(g.get('total_copy_bytes',{}).get('median',0)/2**20,2),
              'copy ms',round(g.get('total_copy_probe_ms',{}).get('median',0),2))
