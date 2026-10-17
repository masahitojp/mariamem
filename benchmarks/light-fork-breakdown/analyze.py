"""Replay phase sums and nested timing envelopes without adding medians."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import statistics


def summary(v):return {'n':len(v),'median_ms':statistics.median(v),'min_ms':min(v),'max_ms':max(v),'all_ms':v}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);a=p.parse_args();e=a.workspace/'evidence'
    receipt=json.loads((e/'receipt.json').read_text());assert receipt['completed'] and len(receipt['cells'])==20
    groups={False:collections.defaultdict(list),True:collections.defaultdict(list)};detail=collections.defaultdict(list);records=[]
    for row in receipt['cells']:
        path=e/(row['name']+'.json');assert hashlib.sha256(path.read_bytes()).hexdigest()==row['result_sha256'];d=json.loads(path.read_text());m=d['final_go']['linear_memory_virtual'];assert m['creates']==m['releases']==5 and m['active_mappings']==m['active_reserved_bytes']==m['active_rw_bytes']==m['release_failures']==0
        phase=collections.defaultdict(float)
        for op in d['operations']:phase[op['name'].rstrip('0123456789_')]+=op['seconds']*1000
        phase['whole_product']=d['suite_product_seconds']*1000;phase['whole_observed']=d['suite_seconds']*1000;phase['prepare']=phase['prepare_start']+phase['prepare_setup'];phase['SQL']=sum(phase[n] for n in ['point_use','count_use','mutation'])
        for k,v in phase.items():groups[row['traced']][k].append(v)
        r=dict(name=row['name'],trial=row['trial'],traced=row['traced'],phase_ms=dict(phase))
        if row['traced']:
            paths=sorted((e/row['name']).glob('*.json'),key=lambda p:int(p.stem.rsplit('-',1)[1]));traces=[json.loads(p.read_text()) for p in paths];by=collections.defaultdict(list)
            for t in traces:by[t['operation']].append(t)
            def events(t):return {v['name']:v['offset_ns']/1e6 for v in t['events']}
            freeze=events(by['snapshot_freeze'][0]);own=events(by['snapshot_own'][0]);capture=events(by['snapshot_capture'][0]);finishes=[events(t) for t in by['finish_breakdown']]
            assert len(finishes)==5
            x={'freeze_total':freeze['end']-freeze['begin'],'freeze_source_hash_and_transfer':freeze['source_inventory_hashed']-freeze['begin'],'freeze_target_verify_and_metadata':freeze['target_verified']-freeze['source_inventory_hashed'],'own_verify':own['end']-own['begin'],'snapshot_finish':capture['finish_returned']-capture['before_finish'],'snapshot_preconditions':capture['preconditions_checked']-capture['begin'],'snapshot_capture_total':capture['end']-capture['begin']}
            x['snapshot_finish_outside_freeze']=x['snapshot_finish']-x['freeze_total'];assert x['snapshot_finish_outside_freeze']>=0
            x['child_finish_total']=sum(f['end']-f['begin'] for f in finishes[1:]);x['child_shutdown_call']=sum(f['shutdown_call_returned']-f['shutdown_call_begin'] for f in finishes[1:]);x['child_session_drain']=sum(f['session_workers_drained']-f['begin'] for f in finishes[1:])
            starts=[events(t) for t in by['startup']];assert len(starts)==5
            x['fork_linked_to_ready_header']=sum(t['ready_header_received']-t['linked_execution_begin'] for t in starts[1:]);x['fork_startup_total']=sum(t['end']-t['begin'] for t in starts[1:]);x['fork_before_linked']=sum(t['linked_execution_begin']-t['begin'] for t in starts[1:]);x['fork_after_ready_header']=sum(t['end']-t['ready_header_received'] for t in starts[1:])
            api=[events(t) for t in by['api_startup']];assert len(api)==5
            x['fork_api_pre_directory']=sum(t['runtime_directory_ready']-t['options_ready'] for t in api[1:])
            x['fork_api_host_call']=sum(t['host_returned']-t['runtime_directory_ready'] for t in api[1:])
            x['fork_api_host_call_outside_startup']=x['fork_api_host_call']-x['fork_startup_total']
            for k,v in x.items():detail[k].append(v)
            r.update(detail_ms=x,traces=traces)
        records.append(r)
    out={'completed_executions':20,'DB_lifecycles':100,'cohorts':{str(k):{n:summary(v) for n,v in g.items()} for k,g in groups.items()},'detail':{k:summary(v) for k,v in detail.items()},'records':records,'limits':['Go 1-table/1-row/4-child app-connections fixture; not established identical to supplied Linux/pgmem workload.','Trace off/on are separate cohorts; no pgmem or Linux measurements.','Snapshot finish contains freeze; outside-freeze is nested duration subtraction, not pure InnoDB shutdown.','Trace writes and guest diagnostics can perturb workload; all observations retained.','Each sum is calculated per execution before summary; different medians do not sum to a median whole.']}
    (e/'analysis.json').write_text(json.dumps(out,indent=2)+'\n')
    for k,g in out['cohorts'].items():print(k,{n:round(g[n]['median_ms'],3) for n in ['whole_product','prepare','snapshot','fork_ready','SQL','child_close','snapshot_close']})
    print('DETAIL',{k:round(v['median_ms'],3) for k,v in out['detail'].items()});print('PASS: 20 hashed observations; SQL/cleanup and all traced phase counts')


if __name__=='__main__':main()
