"""Read-only reduction from preserved process records, independent of build/temp."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parent

def reduce_record(r):
    assert r['result']=='PASS' and r['exit_code']==0 and r['cap']==1
    assert len(r['children'])==4 and not r['scratch_remaining']
    assert all(r['cleanup'][k]==0 for k in ('active_mappings','active_rw_bytes','active_reserved_bytes','release_failures'))
    rows=[]
    for c in r['children']:
        assert c['oracle'] and c['fork_wall_ns']>0 and c['fork_cpu_ns']>0
        v={'fork_wall':c['fork_wall_ns'],'fork_cpu':c['fork_cpu_ns'],'sql':c['sql_wall_ns'],'close':c['close_wall_ns']}
        if r['traced']:
            events=c['events'];h={e['name']:e['offset_ns'] for e in events}
            assert len(h)==len(events),'duplicate marker'
            assert all(0<=x<=c['fork_wall_ns'] for x in h.values())
            boundaries=[0,h['fork/snapshot_handle_ready'],h['runtime/filesystem_begin'],h['runtime/prepared_handles_ready'],h['runtime/reserve_begin'],h['runtime/reserve_end'],h['runtime/construct_begin'],h['runtime/construct_end'],h['runtime/guest_execute_begin'],h['startup/ready_response_observed'],c['fork_wall_ns']]
            assert boundaries==sorted(boundaries),'nonmonotonic synchronous boundary'
            names=['admission_and_handle','handle_to_filesystem','filesystem_environment_and_handles','before_reserve','memory_reserve','reserve_to_construct','memory_construct','construct_to_execute','execute_to_ready_response','ready_response_to_return']
            v.update({name:b-a for name,a,b in zip(names,boundaries,boundaries[1:])})
            assert sum(v[k] for k in names)==c['fork_wall_ns']
            v['snapshot_acquire']=h['startup/metadata_snapshot_validated']-h['startup/native_identity_checked']
            v['prepared_handles']=h['runtime/prepared_handles_ready']-h['runtime/prepared_handles_begin']
            v['ready_header_to_observed']=h['startup/ready_response_observed']-h['startup/ready_header_received']
            v['ready_observed_to_listener']=h['startup/wire_listener_ready']-h['startup/ready_response_observed']
            g={e['name']:e['offset_ns'] for e in c['guest']['events']}
            assert len(g)==len(c['guest']['events'])
            guestkeys=['guest_main','restore_begin','restore_complete','open_begin','server_init_begin','server_init_complete','bootstrap_complete','routine_schema_begin','routine_schema_complete','ready_prepared']
            assert [g[k] for k in guestkeys]==sorted(g[k] for k in guestkeys)
            v.update({'guest_before_open':g['open_begin']-g['guest_main'],
                'guest_open_before_server_init':g['server_init_begin']-g['open_begin'],
                'guest_server_init':g['server_init_complete']-g['server_init_begin'],
                'guest_server_init_to_routine':g['routine_schema_begin']-g['server_init_complete'],
                'guest_routine_schema':g['routine_schema_complete']-g['routine_schema_begin'],
                'guest_routine_to_ready':g['ready_prepared']-g['routine_schema_complete'],
                'guest_total':g['ready_prepared']-g['guest_main'],
                'guest_restore':g['restore_complete']-g['restore_begin']})
            v['execute_ready_residual']=v['execute_to_ready_response']-v['guest_total']
            assert v['execute_ready_residual']>=0
        rows.append(v)
    return {k:statistics.median(v[k] for v in rows)/1e6 for k in rows[0]}

def summarize(directory):
    records={f'{i}-{mode}':json.loads((directory/f'round{i}-{mode}.json').read_text()) for i in range(5) for mode in ('plain','traced')}
    per={name:reduce_record(record) for name,record in records.items()}
    summary={}
    for mode in ('plain','traced'):
        cells=[per[f'{i}-{mode}'] for i in range(5)]
        summary[mode]={k:{'p50_ms':statistics.median(c[k] for c in cells),'range_ms':[min(c[k] for c in cells),max(c[k] for c in cells)],'process_medians_ms':[c[k] for c in cells]} for k in cells[0]}
    summary['calibration']={'paired_fork_wall_percent':[(per[f'{i}-traced']['fork_wall']/per[f'{i}-plain']['fork_wall']-1)*100 for i in range(5)],'plain_and_traced_same_overlay_binary':True}
    summary['method']='4-child median within process; median across 5 fresh processes; nested columns are not additive across medians'
    return summary

def controls(d):
    r=json.loads((d/'round0-traced.json').read_text())
    for kind in ('missing_marker','failed_oracle','mapping_leak'):
        bad=copy.deepcopy(r)
        if kind=='missing_marker':bad['children'][0]['events']=[e for e in bad['children'][0]['events'] if e['name']!='runtime/prepared_handles_ready']
        elif kind=='failed_oracle':bad['children'][0]['oracle']=False
        else:bad['cleanup']['active_mappings']=1
        try:reduce_record(bad)
        except (AssertionError,KeyError):pass
        else:raise AssertionError('accepted '+kind)
    negative=json.loads((d/'negative.json').read_text())
    assert negative['result']=='FAIL' and negative['exit_code']==1 and 'seed oracle' in negative['error']
    assert not negative['scratch_remaining'] and negative['cleanup']['active_mappings']==0

def main():
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,default=ROOT/'results');p.add_argument('--check',action='store_true');a=p.parse_args();d=a.results
    controls(d);s=summarize(d)
    if a.check:
        assert json.loads((d/'summary.json').read_text())==s,'summary differs'
        for name,sha in json.loads((d/'SHA256SUMS.json').read_text()).items():assert hashlib.sha256((d/name).read_bytes()).hexdigest()==sha,name
        print('PASS: read-only reduction, checksums, negative oracle, 3 analysis mutations')
    else:(d/'summary.json').write_text(json.dumps(s,indent=2)+'\n')
if __name__=='__main__':main()
