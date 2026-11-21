"""Validate all retained rows and calculate paired wall/CPU and trace differences."""
from collections import Counter,defaultdict
import csv
import gzip
import json
from pathlib import Path
from statistics import mean,median
import sys
from campaign import MODES,jobs,validate,verify_output

def write(path,rows):
    with path.open('w') as f:
        w=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n')
        w.writeheader()
        for row in rows:
            w.writerow({k:round(v,7) if isinstance(v,float) else v for k,v in row.items()})

def run(p):
    counts=Counter()
    primary={};trace={}; defs={}; sizes={}
    stage_names=['client_to_wire','wire_prepare','monitor_to_call','call_to_queue_slot','sender_start','write_to_input',
        'input_to_worker','worker_to_sql','sql','sql_to_reply','reply_to_stdout','stdout_to_header','header_to_body',
        'json_decode','id_dispatch','notify_to_caller','caller_to_monitor','monitor_join','build_wire_reply','wire_to_client']
    files={x.name for x in (p/'runs').iterdir()}
    env=json.loads((p/'environment.json').read_bytes())
    assert env['binaries']['raw']['sha256']!=env['binaries']['trace']['sha256']
    for binary,b,sql,mode,n in jobs():
        tag=f'{binary}-{b}-{sql}-{mode}'
        files.remove(tag+'.jsonl')
        obs=[json.loads(line) for line in (p/'runs'/(tag+'.jsonl')).read_text().splitlines()]
        verify_output(obs,sql,n)
        assert defs.setdefault(sql,obs[0]['registered'])==obs[0]['registered']
        groups=obs[1:]
        counts['processes']+=1;counts['databases']+=n;counts['inserts']+=n*100
        if binary=='trace':
            files.remove(tag+'.json.gz')
            batches=json.loads(gzip.decompress((p/'runs'/(tag+'.json.gz')).read_bytes()))
            validate(batches,groups,sql)
            counts['traced']+=n*100
            for group in batches:
                pattern=tuple((r['RequestBytes'],r['ResponseBytes'],r['Slot']) for r in group)
                assert sizes.setdefault(sql,pattern)==pattern
        if not b:continue
        counts[binary+'_steady']+=(n-2)*100
        if binary=='raw':
            primary[b,sql,mode]={k:mean(x[f] for x in groups[2:])/1e6 for k,f in [('wall','raw_ns'),('cpu','process_cpu_ns')]}
            continue
        st=Counter()
        for group in batches[2:]:
            for r in group:
                t=r['T']
                for name,start,end in zip(stage_names,t,t[1:]):st[name]+=end-start
                st['exec']+=t[-1]-t[0]
                st['trigger']+=r['TriggerNS']
        assert sum(st[k] for k in stage_names)==st['exec']
        st['outside_sql']=st['exec']-st['sql']
        st['pre_sql']=sum(st[k] for k in stage_names[:8])
        st['post_sql']=sum(st[k] for k in stage_names[9:])
        assert st['pre_sql']+st['post_sql']==st['outside_sql']
        trace[b,sql,mode]={k:v/((n-2)*1e6) for k,v in st.items()}
    assert not files,files
    assert counts==dict(processes=150,databases=1536,inserts=153600,traced=44400,raw_steady=90000,trace_steady=36000),counts
    pairs=[];summary=[]
    for sql in 'ABC':
        for mode in MODES[1:]:
            for measure in ('wall','cpu'):
                subset=[]
                for b in range(1,7):
                    a=primary[b,sql,'os1'][measure];z=primary[b,sql,'os2'][measure]
                    reference=(a+z)/2
                    value=primary[b,sql,mode][measure]
                    delta=reference-value
                    row=dict(sql=sql,mode=mode,metric=measure,block=b,os_first=a,os_last=z,os_mean=reference,
                             candidate=value,saved_ms=delta,saved_pct=100*delta/reference,os_drift_ms=abs(a-z))
                    subset.append(row);pairs.append(row)
                col=lambda k:[r[k] for r in subset]
                ds=col('saved_ms'); positive=sum(x>0 for x in ds); drift=median(col('os_drift_ms'))
                summary.append(dict(sql=sql,mode=mode,metric=measure,mean_os=mean(col('os_mean')),mean_candidate=mean(col('candidate')),
                        median_saved=median(ds),median_pct=median(col('saved_pct')),min_saved=min(ds),max_saved=max(ds),
                        positive=positive,median_os_drift=drift,passes=positive>=5 and median(ds)>drift))
    write(p/'raw-pairs.csv',pairs);write(p/'raw-summary.csv',summary)
    interaction=[]
    for sql in 'ABC':
        for b in range(1,7):
            for metric in ('wall','cpu'):
                baseline=(primary[b,sql,'os1'][metric]+primary[b,sql,'os2'][metric])/2
                inp=primary[b,sql,'input'][metric];out=primary[b,sql,'output'][metric];both=primary[b,sql,'both'][metric]
                interaction.append(dict(sql=sql,block=b,metric=metric,extra_saving_beyond_sum_ms=inp+out-both-baseline))
    write(p/'interaction.csv',interaction)
    stages=[];ts=[]
    for sql in 'ABC':
        for mode in MODES:
            for field in trace[1,sql,'os']:
                ds=[];vals=[];base=[]
                for b in range(1,4):
                    v=trace[b,sql,mode][field];a=trace[b,sql,'os'][field]
                    vals.append(v);base.append(a);ds.append(a-v)
                    stages.append(dict(block=b,sql=sql,mode=mode,stage=field,ms100=v,saved_vs_os=a-v))
                ts.append(dict(sql=sql,mode=mode,stage=field,os=mean(base),value=mean(vals),mean_saved=mean(ds),
                               min_saved=min(ds),max_saved=max(ds)))
    write(p/'stages-by-block.csv',stages);write(p/'stages.csv',ts)
    (p/'verification.json').write_text(json.dumps(dict(totals=counts,request_bytes=97,response_min=214,response_max=217,
           equal_frame_length_and_slot_by_ordinal=True,registered_sql_conditions=sorted(defs)),indent=2)+'\n')
if __name__=='__main__':run(Path(sys.argv[1]))
