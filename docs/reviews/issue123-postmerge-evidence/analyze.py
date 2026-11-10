"""Reduce the fixed campaign without dropping slow observations."""
from pathlib import Path
import csv
import io
import hashlib
import json
import statistics as st
import sys


def quantile(values, p):
    values = sorted(values)
    if not values:
        return None
    n = (len(values)-1)*p
    low = int(n)
    return values[low] + (values[min(low+1,len(values)-1)]-values[low])*(n-low)


def stats(values):
    return dict(count=len(values),p50=quantile(values,.5),p95=quantile(values,.95),
                maximum=max(values) if values else None,over_100ms=sum(v>100 for v in values))


check = '--check' in sys.argv
args = [a for a in sys.argv[1:] if a != '--check']
e = Path(args[0]) if args else Path(__file__).resolve().parent
def save(name, data):
    path = e/name
    if check:
        assert path.read_text() == data, name+' differs'
    else:
        path.write_text(data)
raw = e/'observations.json'
records = json.loads(raw.read_text()) if raw.exists() else []
assert not records or len(records)==56
reduced=[] if records else json.loads((e/'trials.json').read_text())['trials']
for r in records:
    report=r['report']
    if report['cleanup']:
        assert all(s['cleanup'] for s in report['samples'])
        assert all(report['cleanup_stats'][k]==0 for k in ('active_mappings','active_rw_bytes','active_reserved_bytes','release_failures'))
    negative = r['negative']
    if negative:
        assert r['exit_code']==1 and not report['success'] and 'pristine oracle' in report['error'] and report['cleanup']
    elif not report['success'] or not report['cleanup']:
        assert r['exit_code']!=0 and report.get('error')
    else:
        assert r['exit_code']==0
    if not negative and report['success']:
        assert len(report['samples'])==r['count'] and all(s['oracle'] for s in report['samples'])
    phases={}
    tails=[]
    for sample in report['samples']:
        for span in sample['spans']:
            value=span['end_ms']-span['begin_ms']
            phases.setdefault(span['name'],[]).append(value)
            if value>100:
                tails.append(dict(index=sample['index'],lane=sample['lane'],phase=span['name'],ms=value))
    result={k:r[k] for k in ('variant','mode','parallel','rep','kind','negative','count','exit_code','external_process_ms')}
    result.update({k:report[k] for k in ('suite_ms','suite_cpu_ms','batch_ms','batch_cpu_ms','lifetime_max_rss_bytes','max_active','resolved_max_forks','cleanup','success')})
    result.update(root_ms={s['name']:s['end_ms']-s['begin_ms'] for s in report['root_spans']},
                  phases_ms={name:stats(values) for name,values in phases.items()},tails=tails,
                  completed=len(report['samples']),oracles_passed=sum(s['oracle'] for s in report['samples']),
                  error=report.get('error'),cleanup_stats=report['cleanup_stats'])
    reduced.append(result)
if records:
    save('trials.json',json.dumps({'observations_sha256':hashlib.sha256(raw.read_bytes()).hexdigest(),'trials':reduced},separators=(',',':'))+'\n')
assert len(reduced)==56
summary=[]
for mode in ('fresh','fork'):
    for parallel in (1,4):
        pair={a:sorted([r for r in reduced if r['kind']=='primary' and r['variant']==a and r['mode']==mode and r['parallel']==parallel],key=lambda r:r['rep']) for a in ('before','after')}
        assert all([r['rep'] for r in group]==list(range(5)) for group in pair.values())
        failed=[{'variant':a,'rep':r['rep'],'error':r['error']} for a in pair for r in pair[a] if not r['success'] or not r['cleanup']]
        valid=[i for i in range(5) if all(pair[a][i]['success'] and pair[a][i]['cleanup'] for a in pair)]
        pair={a:[group[i] for i in valid] for a,group in pair.items()}
        cell={'mode':mode,'parallel':parallel,'planned_pairs':5,'successful_pairs':len(valid),'failed_trials':failed,'metrics':{}}
        assert valid, 'No successful pairs; no speed summary possible'
        metrics={k:(lambda r,k=k:r[k]) for k in ('suite_ms','suite_cpu_ms','batch_ms','batch_cpu_ms','external_process_ms')}
        metrics['peak_rss_mib']=lambda r:r['lifetime_max_rss_bytes']/(1<<20)
        metrics['start_or_fork_p50_ms']=lambda r:r['phases_ms']['start_or_fork']['p50']
        metrics['start_or_fork_p95_ms']=lambda r:r['phases_ms']['start_or_fork']['p95']
        metrics['retire_p50_ms']=lambda r:r['phases_ms']['retire']['p50']
        metrics['close_p50_ms']=lambda r:r['phases_ms']['close']['p50']
        if mode=='fork':
            for name in ('root_start','root_seed','snapshot'):
                metrics[name+'_ms']=lambda r,name=name:r['root_ms'][name]
        for name,read in metrics.items():
            before=[read(r) for r in pair['before']]; after=[read(r) for r in pair['after']]
            cell['metrics'][name]={'before_median':st.median(before),'after_median':st.median(after),
                'median_paired_delta':st.median(b-a for a,b in zip(before,after)),
                'median_paired_percent':st.median((b/a-1)*100 for a,b in zip(before,after)),
                'after_lower_pairs':sum(b<a for a,b in zip(before,after)),
                'before_range':[min(before),max(before)],'after_range':[min(after),max(after)]}
        cell['start_or_fork_over_100ms']={a:sum(r['phases_ms']['start_or_fork']['over_100ms'] for r in pair[a]) for a in pair}
        cell['sql_over_100ms']={a:sum(s['over_100ms'] for r in pair[a] for name,s in r['phases_ms'].items() if name in ('seed','select1','count_sum','update','verify_update')) for a in pair}
        summary.append(cell)
save('summary.json',json.dumps(summary,indent=2)+'\n')
with io.StringIO(newline='') as f:
    w=csv.writer(f); w.writerow(['mode','parallel','metric','before_median','after_median','median_paired_percent','after_lower_pairs'])
    for cell in summary:
        for metric,values in cell['metrics'].items():
            w.writerow([cell['mode'],cell['parallel'],metric,values['before_median'],values['after_median'],values['median_paired_percent'],values['after_lower_pairs']])
    save('summary.csv',f.getvalue().replace('\r\n','\n'))
for cell in summary:
    print(cell['mode'],cell['parallel'],json.dumps({k:cell['metrics'][k] for k in ('suite_ms','suite_cpu_ms','start_or_fork_p50_ms','peak_rss_mib')}))
