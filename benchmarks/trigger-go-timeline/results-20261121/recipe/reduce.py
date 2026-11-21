"""Produce additive stage totals per 100 requests, then compare paired controls."""
from collections import defaultdict
import csv
import gzip
import json
from pathlib import Path
from statistics import mean,median
import sys
from campaign import tracecheck

stages=['client_to_wire','wire_prepare','monitor_to_call','call_to_queue_slot','sender_start',
        'send_to_guest_input','input_to_worker','worker_to_sql','sql','sql_to_reply',
        'reply_to_stdout','stdout_to_host_header','header_to_body','json_decode','id_dispatch',
        'notify_to_caller','caller_to_monitor','monitor_join','build_wire_reply','wire_send_to_exec_return']
def write(path,rows):
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n')
        writer.writeheader()
        for row in rows: writer.writerow({k:round(v,6) if isinstance(v,float) else v for k,v in row.items()})
def main():
    out=Path(sys.argv[1])
    dst=out/'runs';blocks=[];controls=[];stats=[];frames=[]
    for block in range(1,4):
        for sql in 'ABC':
            name=f'{block}-{sql}'
            ns={}
            for mode in ('base','on'):
                lines=[json.loads(s) for s in (dst/(name+'-'+mode+'.jsonl')).read_text().splitlines()]
                assert len(lines)==13 and lines[0]['arm']==sql
                ns[mode]=lines[1:]
            trace=json.loads(gzip.decompress((dst/(name+'-on.json.gz')).read_bytes()))
            tracecheck(trace,ns['on'],sql)
            totals=defaultdict(int)
            for rows in trace[2:]:
                for r in rows:
                    ts=r['T']
                    for k,start,end in zip(stages,ts,ts[1:]): totals[k]+=end-start
                    totals['trigger_inclusive']+=r['TriggerNS']
                    totals['exec']+=ts[-1]-ts[0]
            assert sum(totals[k] for k in stages)==totals['exec']
            totals['sql_other']=totals['sql']-totals['trigger_inclusive']
            totals['outer_go']=totals['exec']-totals['sql']
            totals['pre_sql']=sum(totals[k] for k in stages[:8])
            totals['post_sql']=sum(totals[k] for k in stages[9:])
            row={'block':block,'sql_arm':sql,**{k:v/1e7 for k,v in totals.items()}}
            blocks.append(row)
            meanraw={k:mean(r['raw_ns']/1e6 for r in data[2:]) for k,data in ns.items()}
            controls.append(dict(block=block,sql_arm=sql,base_raw_ms=meanraw['base'],on_raw_ms=meanraw['on'],
                on_vs_base_pct=100*(meanraw['on']/meanraw['base']-1),
                on_loop_outside_exec_ms=meanraw['on']-row['exec']))
            for key in ('RequestBytes','ResponseBytes','TriggerCalls'):
                vals=[r[key] for batch in trace[2:] for r in batch]
                frames.append(dict(block=block,arm=sql,metric=key,min=min(vals),max=max(vals),mean=mean(vals)))
    for stage in stages+['trigger_inclusive','sql_other','pre_sql','post_sql','outer_go','exec']:
        a,b,c=[[r[stage] for r in blocks if r['sql_arm']==s] for s in 'ABC']
        stats.append(dict(stage=stage,A_mean=mean(a),B_mean=mean(b),C_mean=mean(c),
            A_minus_B=mean(a)-mean(b),A_minus_C=mean(a)-mean(c),
            A_min=min(a),A_max=max(a),A_pct=100*mean(a)/mean(r['exec'] for r in blocks if r['sql_arm']=='A')))
    groups={
        'client_prepare_send':stages[:5],
        'input_and_worker':stages[5:8],
        'sql_except_trigger':['sql_other'],
        'outermost_trigger':['trigger_inclusive'],
        'reply_build_and_read':stages[9:13],
        'json_decode':['json_decode'],
        'id_delivery':stages[14:17],
        'monitor_join':['monitor_join'],
        'wire_result_to_client':stages[18:20],
    }
    grouped=[]
    for label,members in groups.items():
        vals={arm:mean(sum(r[k] for k in members) for r in blocks if r['sql_arm']==arm) for arm in 'ABC'}
        grouped.append(dict(stage=label,**vals,A_minus_B=vals['A']-vals['B']))
    for arm in 'ABC':
        assert abs(sum(r[arm] for r in grouped)-mean(r['exec'] for r in blocks if r['sql_arm']==arm))<1e-10
    write(out/'grouped.csv',grouped)
    write(out/'blocks.csv',blocks);write(out/'stages.csv',stats)
    write(out/'observer-cost.csv',controls);write(out/'frame-sizes.csv',frames)
if __name__=='__main__':main()
