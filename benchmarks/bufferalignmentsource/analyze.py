"""Recompute a finite Issue63 summary from compact observations, including after cleanup."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics


def dump(value):
    return json.dumps(value, indent=2, sort_keys=True)+'\n'


def summarize(records):
    assert len(records)==38, 'incomplete fixed campaign'
    assert len({r['key'] for r in records})==38
    measured=[r for r in records if isinstance(r['rep'],int)]
    expected={(variant,mode,p,rep) for variant in ['baseline','candidate']
              for mode,p in [('serial',8),('batch',8),('batch',4)] for rep in range(5)}
    assert {(r['variant'],r['mode'],r['parallel'],r['rep']) for r in measured}==expected
    negatives=[r for r in records if r['negative']]
    assert {r['variant'] for r in negatives}=={'baseline','candidate'} and len(negatives)==2
    for r in records:
        v=r['result']
        assert v['cleanup'] and all(v['mapping_after_close'][k]==0 for k in
                ['active_mappings','active_rw_bytes','active_reserved_bytes'])
        assert v['go']=='go1.26.10' and v['gomaxprocs']==8
        assert (v['profile']['read'],v['profile']['write'],v['profile']['purge'],v['profile']['native_aio'])==(1,2,1,0)
        if r['negative']:
            assert r['exit_code']!=0 and not v['success'] and 'pristine oracle' in v['error']
        else:
            assert r['exit_code']==0 and v['success']
            assert v['count']==(4 if r['mode']=='serial' else 48)
        if r['mode']=='serial' and not r['negative']:
            assert len(v['forks'])==4
            assert set(r['rss_bytes'])=={'baseline','child-1','child-2','child-3','child-4','closed'}
            assert all(n>0 for n in r['rss_bytes'].values())
    metrics={}
    for name in ['fork_wall_ms','fork_cpu_ms','held1_rss_mib','held2_rss_mib','held4_rss_mib','batch_p8_ms','batch_p4_ms']:
        values={}
        for variant in ['baseline','candidate']:
            vals=[]
            for rep in range(5):
                mode='batch' if name.startswith('batch') else 'serial'
                parallel=4 if name=='batch_p4_ms' else 8
                r=next(r for r in measured if (r['variant'],r['mode'],r['parallel'],r['rep'])==(variant,mode,parallel,rep))
                if name.startswith('fork'):
                    key='wall_ms' if name=='fork_wall_ms' else 'cpu_ms'
                    val=statistics.median(c[key] for c in r['result']['forks'])
                elif name.startswith('held'):
                    child=int(name[4]);rss=r['rss_bytes'];val=(rss[f'child-{child}']-rss['baseline'])/2**20
                else:val=r['result']['batch_ms']
                vals.append(val)
            values[variant]={'values':vals,'median':statistics.median(vals)}
        pairs=[b-a for a,b in zip(values['baseline']['values'],values['candidate']['values'])]
        percentages=[(b/a-1)*100 for a,b in zip(values['baseline']['values'],values['candidate']['values'])]
        metrics[name]={**values,'paired_deltas':pairs,'paired_percentages':percentages,
                       'median_paired_delta':statistics.median(pairs),
                       'median_paired_percentage':statistics.median(percentages),
                       'improved_pairs':sum(p<0 for p in pairs),'worse_pairs':sum(p>0 for p in pairs)}
    return {'metrics':metrics,'correctness':'PASS in all observed runs; two deliberate oracle failures detected and cleaned',
            'measured_serial_children':40,'measured_batch_children':960,
            'queue':'N/A: no reviewed binding of queue probes to new guest',
            'overall_four_field_adoption':'INCONCLUSIVE',
            'scope':'one non-isolated macOS arm64 host; five fresh-process pairs; descriptive, not significance or platform qualification'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results',type=Path,default=Path(__file__).resolve().parent)
    p.add_argument('--check',action='store_true')
    args=p.parse_args();root=args.results
    records=json.loads((root/'observations.json').read_text())
    result=dump(summarize(records))
    if args.check:
        assert (root/'summary.json').read_text()==result
        for name,expected in json.loads((root/'SHA256SUMS.json').read_text()).items():
            assert hashlib.sha256((root/name).read_bytes()).hexdigest()==expected,name
        print('PASS read-only recomputation and checksums')
    else:
        (root/'summary.json').write_text(result)
        print(result)


if __name__=='__main__':main()
