"""Compact, read-only recomputation of stage diagnostics and CPU profile tables."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from statistics import median

STAGES=['baseline',*[f'child{i}_{stage}' for i in [1,2] for stage in ['reserve','construct','ready','checked']], 'after_content_comparison','closed_children']

def stat(values):
    return dict(median=round(median(values),6),minimum=round(min(values),6),maximum=round(max(values),6),n=len(values))

def profile(text):
    total=float(re.search(r'Total samples = ([0-9.]+)ms',text).group(1))
    rows={}
    for line in text.splitlines():
        parts=line.split()
        if len(parts)>=6 and re.fullmatch(r'[0-9.]+(?:ms)?',parts[0]) and parts[1].endswith('%'):
            flat=float(parts[0].removesuffix('ms'));cum=float(parts[3].removesuffix('ms'));name=parts[5]
            selected={'syscall.Mprotect','syscall.Mmap','syscall.Munmap','runtime.pthread_cond_signal','runtime.pthread_cond_wait','runtime.memclrNoHeapPointers','runtime.memmove','syscall.rawsyscalln'}
            if name in selected or name.endswith(('.newMemoryModule','.MemoryFill','.MemoryInit','.(*MemoryMapping).Grow')):
                rows[name]=dict(flat_ms=flat,cum_ms=cum,flat_percent=round(flat/total*100,6),cum_percent=round(cum/total*100,6))
    assert total>0 and rows
    return dict(total_cpu_samples_ms=total,functions=rows)

def summarize(data):
    assert len(data['stages'])==5 and len(data['profiles'])==2
    groups=[]
    for i,item in enumerate(data['stages']):
        assert item['repetition']==i
        d=item['result'];assert d['success'] and d['cleanup_complete']
        assert [x['stage'] for x in d['events']]==STAGES
        assert [x['stage'] for x in item['rss']]==STAGES
        es={x['stage']:x for x in d['events']};rss={x['stage']:x['rss_bytes'] for x in item['rss']}
        assert es['closed_children']['mapping']['active_mappings']==0
        assert es['child2_checked']['mapping']['active_rw_bytes']==sum(es[f'child{j}_checked']['guest_observed_bytes'] for j in [1,2])
        for event in es.values():
            assert 0<=event['guest_resident_bytes']<=event['guest_observed_bytes']
            assert event['wall_ms']>=0 and event['cpu_ms']>=0
        comp=d['comparison'];assert comp['page_bytes']==16384
        assert comp['both_resident_pages']==comp['same_zero_pages']+comp['same_nonzero_pages']+comp['different_pages']
        groups.append((es,rss,comp))
    out=dict(stages={},comparison={},profiles=[])
    for stage in ['reserve','construct','ready','checked']:
        out['stages'][stage]={}
        for metric in ((['cpu_ms','wall_ms'] if stage in ['reserve','construct'] else []) + ['guest_resident_bytes','guest_observed_bytes']):
            out['stages'][stage][metric]=stat([median([es[f'child{j}_{stage}'][metric] for j in [1,2]]) for es,rss,comp in groups])
        # First child only: avoids counting the already retained previous child in process RSS.
        out['stages'][stage]['first_child_rss_increment_bytes']=stat([rss[f'child1_{stage}']-rss['baseline'] for es,rss,comp in groups])
    out['growth_calls_after_reserve']=stat([median([es[f'child{j}_ready']['mapping']['grow_calls']-es[f'child{j}_reserve']['mapping']['grow_calls'] for j in [1,2]]) for es,rss,comp in groups])
    for key in ['both_resident_pages','same_zero_pages','same_nonzero_pages','different_pages','only_first_resident_pages','only_second_resident_pages']:
        out['comparison'][key.replace('_pages','_bytes')]=stat([comp[key]*comp['page_bytes'] for es,rss,comp in groups])
    for i,item in enumerate(data['profiles']):
        assert item['repetition']==i and item['result']['success'] and item['result']['count']==100
        out['profiles'].append(profile(item['all_functions']))
    return out

def rendered(data):return json.dumps(data,indent=2)+'\n'

def check(path):
    seals=json.loads((path/'SHA256SUMS.json').read_text())
    for name,sha in seals.items():assert hashlib.sha256((path/name).read_bytes()).hexdigest()==sha,name
    calculated=summarize(json.loads((path/'observations.json').read_text()))
    assert (path/'summary.json').read_text()==rendered(calculated),'summary mismatch'
    assert json.loads((path/'completion.json').read_text())['result']=='PASS'
    return calculated

def main():
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--collect',type=Path);p.add_argument('--check',action='store_true');a=p.parse_args()
    if a.check:
        assert a.collect is None;check(a.results);print('PASS: hashes, campaign completeness, full-span/page partition checks, recomputed summary; read-only');return
    assert a.collect is not None
    d=dict(stages=[],profiles=[])
    for i in range(5):d['stages'].append(dict(repetition=i,result=json.loads((a.collect/f'measure/stages-{i}.json').read_text()),rss=json.loads((a.collect/f'measure/stages-{i}.rss.json').read_text())))
    for i in range(2):d['profiles'].append(dict(repetition=i,result=json.loads((a.collect/f'measure/profile-{i}.json').read_text()),all_functions=(a.collect/f'measure/profile-{i}-all.txt').read_text()))
    summary=summarize(d);a.results.mkdir(parents=True,exist_ok=True)
    (a.results/'observations.json').write_text(json.dumps(d,separators=(',',':'))+'\n');(a.results/'summary.json').write_text(rendered(summary))

if __name__=='__main__':main()
