"""Fail-closed compact report; parallel wall time is not summed operation time."""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics


def percentile(values,p):
    return sorted(values)[math.ceil(len(values)*p)-1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--trials',type=int,default=3)
    parser.add_argument('--forks',type=int,default=16)
    args=parser.parse_args()
    rows=[]
    scaling=[]
    captures=[]
    cases=[('serial',size) for size in (0,10,100)] + [('crud',0),('application',0),('parallel',10),('fdscale',0)]
    for boundary in ('go','import'):
        for case,size in cases:
            for label in ('baseline','candidate'):
                paths=sorted(args.input.glob(f'{boundary}-{case}-{size}-*-{label}.json'))
                expected=1 if case=='fdscale' else args.trials
                if len(paths)!=expected:
                    raise ValueError(f'missing trials: {boundary}/{case}/{size}/{label}: {len(paths)}')
                docs=[json.loads(path.read_text()) for path in paths]
                if case=='fdscale':
                    scaling.append(dict(boundary=boundary,label=label,**{
                        key:docs[0].get(key) for key in ('tables','prepared_files','prepared_bytes','fd_snapshots','fd_snapshots_requested','fd_limit_error','fds_before','fds_snapshot','fds_all_snapshots','fds_after','fd_soft_limit','fd_hard_limit','resources')}))
                    continue
                ready=[op['seconds']*1000 for doc in docs for op in doc['operations'] if op['name'].startswith('fork_ready')]
                if len(ready)!=args.forks*args.trials:
                    raise ValueError(f'missing ready samples: {boundary}/{case}/{size}/{label}')
                preparation=[]
                snapshots=[]
                for doc in docs:
                    preparation.append(sum(op['seconds'] for op in doc['operations'] if op['name'] in ('prepare_start','prepare_setup','snapshot','import')))
                    snapshots.append(sum(op['seconds'] for op in doc['operations'] if op['name'] in ('snapshot','import')))
                rows.append(dict(boundary=boundary,case=case,payload_mib=size,label=label,
                                 workers=docs[0]['workers'],trials=len(docs),fork_samples=len(ready),
                                 ready_p50_ms=statistics.median(ready),ready_p95_ms=percentile(ready,.95),
                                 preparation_s=statistics.median(preparation),
                                 snapshot_or_import_ms=1000*statistics.median(snapshots),
                                 suite_wall_p50_s=statistics.median(doc.get('suite_wall_seconds',doc.get('suite_seconds')) for doc in docs),
                                 suite_wall_p95_s=percentile([doc.get('suite_wall_seconds',doc.get('suite_seconds')) for doc in docs],.95),
                                 suite_cpu_p50_s=statistics.median(doc['suite_cpu_seconds'] for doc in docs),
                                 suite_cpu_scope=docs[0]['suite_cpu_scope'],
                                 sum_operation_p50_s=statistics.median(doc['suite_operation_seconds'] for doc in docs),
                                 suite_product_p50_s=statistics.median(doc['suite_product_seconds'] for doc in docs),
                                 diagnostic_overhead_p50_s=statistics.median(doc['diagnostic_overhead_seconds'] for doc in docs),
                                 fds_before=docs[0].get('fds_before'),fds_snapshot=docs[0].get('fds_snapshot'),fds_after=docs[0].get('fds_after')))
    for size in (0,10,100):
        for label in ('baseline','candidate'):
            docs=[json.loads(path.read_text()) for path in args.input.glob(f'import-capture-{size}-*-{label}.json')]
            if len(docs)!=args.trials:
                raise ValueError(f'missing capture trials: {size}/{label}')
            def median_phase(name):
                return 1000*statistics.median(next(op['seconds'] for op in doc['operations'] if op['name']==name) for doc in docs)
            captures.append(dict(payload_mib=size,label=label,trials=len(docs),
                snapshot_ms=median_phase('snapshot'),persisted_snapshot_ms=median_phase('snapshot_persisted'),
                acquisition_ms=median_phase('import'),source_ready_ms=median_phase('source_ready'),
                suite_product_s=statistics.median(doc['suite_product_seconds'] for doc in docs),
                suite_cpu_s=statistics.median(doc['suite_cpu_seconds'] for doc in docs),
                suite_cpu_scope=docs[0]['suite_cpu_scope']))
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'summary.json').write_text(json.dumps(rows,indent=2)+'\n')
    (args.out/'python-capture.json').write_text(json.dumps(captures,indent=2)+'\n')
    (args.out/'fd-scaling.json').write_text(json.dumps(scaling,indent=2)+'\n')
    with (args.out/'summary.csv').open('w',newline='') as output:
        writer=csv.DictWriter(output,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)


if __name__=='__main__':
    main()
