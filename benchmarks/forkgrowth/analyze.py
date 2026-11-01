"""Replay observed requests arithmetically; never changes an engine's protection."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

PAGE=65536
MAXIMUM=2<<30

def replay(steps,chunk):
    assert steps and steps[0]['old']==0 and steps[0]['next']==256<<20
    logical=steps[0]['next'];enabled=logical;calls=0;peak=0;log=[]
    assert chunk==0 or chunk>0 and chunk%PAGE==0
    for step in steps[1:]:
        assert step['old']==logical and logical<step['next']<=MAXIMUM and step['next']%PAGE==0
        requested=step['next']
        if requested>enabled:
            enabled=requested if chunk==0 else min(MAXIMUM,((requested+chunk-1)//chunk)*chunk)
            calls+=1
        logical=requested;peak=max(peak,enabled-logical)
        assert logical<=enabled<=MAXIMUM
        log.append(dict(logical=logical,enabled=enabled))
    return dict(protection_calls_after_initial=calls,peak_ahead_rw_bytes=peak,final_ahead_rw_bytes=enabled-logical,final_logical_bytes=logical,trace=log)

def summarize(observations):
    assert len(observations)==3
    rows=[]
    for rep,item in enumerate(observations):
        assert item['repetition']==rep
        d=item['result'];assert d['success'] and d['cleanup_complete'] and len(d['children'])==2
        for index,c in enumerate(d['children']):
            assert c['index']==index and c['success'] and c['cleanup_complete']
            assert c['after']['active_mappings']==0 and c['after']['release_failures']==c['before']['release_failures']
            assert c['after']['grow_failures']==c['before']['grow_failures']
            steps=c['steps'];assert len(steps)==c['after']['grow_calls']-c['before']['grow_calls']
            assert all(s['phase']=='fork' for s in steps)
            exact=replay(steps,0);hist=Counter(s['next']-s['old'] for s in steps[1:])
            models={}
            for mib in [0,16,32,64]:
                m=replay(steps,mib<<20)
                assert [x['logical'] for x in m['trace']]==[x['next'] for x in steps[1:]]
                m.pop('trace');models[str(mib)]=m
            rows.append(dict(repetition=rep,child=index,growth_count=len(steps)-1,total_growth_bytes=steps[-1]['next']-steps[0]['next'],delta_histogram={str(k):v for k,v in sorted(hist.items())},models=models))
    return dict(status='OBSERVED_BASELINE_AND_ARITHMETIC_MODELS_ONLY',initial_bytes=256<<20,maximum_bytes=MAXIMUM,model_warning='Lookahead changes OS protection boundary; no optimized execution, equivalence or speedup accepted',rows=rows)

def rendered(x):return json.dumps(x,indent=2)+'\n'
def check(root):
    for name,sha in json.loads((root/'SHA256SUMS.json').read_text()).items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==sha,name
    s=summarize(json.loads((root/'observations.json').read_text()));assert (root/'summary.json').read_text()==rendered(s)
    assert json.loads((root/'completion.json').read_text())['result']=='PASS';return s

def main():
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--collect',type=Path);p.add_argument('--check',action='store_true');a=p.parse_args()
    if a.check:assert a.collect is None;check(a.results);print('PASS: hashes, complete traces, model recomputation; read-only');return
    assert a.collect is not None
    obs=[dict(repetition=i,result=json.loads((a.collect/f'measure/run-{i}.json').read_text())) for i in range(3)]
    summary=summarize(obs);a.results.mkdir(parents=True,exist_ok=True)
    (a.results/'observations.json').write_text(json.dumps(obs,separators=(',',':'))+'\n');(a.results/'summary.json').write_text(rendered(summary))
if __name__=='__main__':main()
