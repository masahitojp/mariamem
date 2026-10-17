"""Compare elapsed suite time; overlapping operation sums are not elapsed time."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import statistics


def summary(v):return dict(n=len(v),median_ms=statistics.median(v),min_ms=min(v),max_ms=max(v),all_ms=v)


def peak(intervals):
    events=sorted([(a,1) for a,b in intervals]+[(b,-1) for a,b in intervals]);active=best=0
    for _,delta in events:active+=delta;best=max(best,active)
    assert active==0
    return best


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);a=p.parse_args();e=a.workspace/'evidence';receipt=json.loads((e/'receipt.json').read_text());assert receipt['completed'] and len(receipt['cells'])==20
    groups={1:collections.defaultdict(list),4:collections.defaultdict(list)};rows=[]
    for cell in receipt['cells']:
        path=e/(cell['name']+'.json');assert hashlib.sha256(path.read_bytes()).hexdigest()==cell['result_sha256'];d=json.loads(path.read_text());assert d['workers']==cell['workers']
        m=d['final_go']['linear_memory_virtual'];assert m['creates']==m['releases']==5 and m['active_mappings']==m['active_reserved_bytes']==m['active_rw_bytes']==m['release_failures']==0
        ops={op['name']:op for op in d['operations']};byphase=collections.defaultdict(float)
        for op in d['operations']:
            assert op['end_ns']>=op['start_ns']
            byphase[op['name'].rstrip('0123456789_')]+=op['seconds']*1000
        values=dict(product=d['suite_product_seconds']*1000,observed=d['suite_seconds']*1000,prepare=byphase['prepare_start']+byphase['prepare_setup'],snapshot=byphase['snapshot'],four_child_elapsed=d['instance_suite_wall_seconds']*1000,baseline_close=byphase['snapshot_close'],fork_operation_sum=byphase['fork_ready'],SQL_operation_sum=sum(byphase[k] for k in ['point_use','count_use','mutation']),disconnect_close_operation_sum=byphase['child_close'])
        r=dict(name=cell['name'],trial=cell['trial'],workers=cell['workers'],values_ms=values,children=[])
        for i in range(4):
            f,c=ops[f'fork_ready_{i:02d}'],ops[f'child_close_{i:02d}'];mu=ops[f'mutation_{i:02d}']
            r['children'].append(dict(index=i,fork_begin_ns=f['start_ns'],fork_ready_ns=f['end_ns'],close_begin_ns=c['start_ns'],close_end_ns=c['end_ns'],mutation_begin_ns=mu['start_ns'],mutation_end_ns=mu['end_ns']))
        r['peak_overlapping_workflows']=peak([(c['fork_begin_ns'],c['close_end_ns']) for c in r['children']])
        r['peak_overlapping_fork_calls']=peak([(c['fork_begin_ns'],c['fork_ready_ns']) for c in r['children']])
        r['peak_overlapping_ready_DBs_before_close']=peak([(c['fork_ready_ns'],c['close_begin_ns']) for c in r['children']])
        r['peak_overlapping_mutation_operations']=peak([(c['mutation_begin_ns'],c['mutation_end_ns']) for c in r['children']])
        assert r['peak_overlapping_workflows']==cell['workers'],r
        if cell['workers']==4:assert r['peak_overlapping_fork_calls']>1,r
        for k,v in values.items():groups[cell['workers']][k].append(v)
        rows.append(r)
    pairs=[]
    for i in range(10):
        serial=next(r for r in rows if r['trial']==i and r['workers']==1);parallel=next(r for r in rows if r['trial']==i and r['workers']==4)
        pairs.append(dict(trial=i,product_change_percent=100*(parallel['values_ms']['product']/serial['values_ms']['product']-1),child_elapsed_change_percent=100*(parallel['values_ms']['four_child_elapsed']/serial['values_ms']['four_child_elapsed']-1)))
    out=dict(completed_executions=20,DB_lifecycles=100,cohorts={str(k):{name:summary(v) for name,v in group.items()} for k,group in groups.items()},records=rows,pairs=pairs,limits=['Four-child wall is the elapsed child-loop envelope; operation sums overlap with workers=4 and are not wall time.','Timestamps show interval overlap, not simultaneous instruction retirement or a hardware-thread count.','Ready DB intervals end before Close begins; they are conservative overlap windows, not an exact active-object counter.','Same benchmark-only observer for both cohorts, trace environment disabled; no unmodified-binary calibration, resource peak, pgmem or Linux measurement.'])
    (e/'analysis.json').write_text(json.dumps(out,indent=2)+'\n')
    for k,g in out['cohorts'].items():print(k,{n:round(v['median_ms'],3) for n,v in g.items()})
    print('OVERLAP',[(r['name'],r['peak_overlapping_fork_calls'],r['peak_overlapping_ready_DBs_before_close'],r['peak_overlapping_mutation_operations']) for r in rows]);print('PASS: all 20 hashes, 100 DB lifecycles and actual workflow/Fork overlap')


if __name__=='__main__':main()
