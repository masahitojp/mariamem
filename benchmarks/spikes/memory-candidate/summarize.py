#!/usr/bin/env python3
"""Preserve every complete timing row; never trim slow trials."""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics

METRICS = ['ready_ms','start_sql_ms','start_fixture_ms','fixture_ms','crud_ms','close_ms','ready_cpu_s','start_sql_cpu_s','start_fixture_cpu_s','fixture_cpu_s','crud_cpu_s','close_cpu_s','total_cpu_s']

def read(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.startswith('{')]

def stats(rows):
    result = {}
    for key in METRICS:
        values = sorted(row[key] for row in rows)
        result[key] = {'p50':statistics.median(values),'mean':statistics.mean(values),'p95':values[math.ceil(.95*len(values))-1],'min':values[0],'max':values[-1]}
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    groups={}; all_rows=[]
    for scenario in ['fresh','repeated']:
        for mode in ['baseline','candidate']:
            paths=sorted(a.evidence.glob('fresh-*-'+mode+'.log')) if scenario=='fresh' else [a.evidence/('repeated-'+mode+'.log')]
            rows=[]
            for trial,path in enumerate(paths):
                for row in read(path):
                    rows.append(row);all_rows.append({'scenario':scenario,'mode':mode,'trial':trial if scenario=='fresh' else 0,**row})
            assert len(rows)==20
            groups[scenario+'-'+mode]={'count':len(rows),'stats':stats(rows),'start_sql_over_500ms':sum(row['start_sql_ms']>500 for row in rows),'fd_minmax':[min(row['fd'] for row in rows),max(row['fd'] for row in rows)],'goroutines_minmax':[min(row['goroutines'] for row in rows),max(row['goroutines'] for row in rows)],'first5':stats(rows[:5]),'last5':stats(rows[-5:])}
    deltas={}
    for scenario in ['fresh','repeated']:
        result={}
        for key in METRICS:
            result[key]={}
            for stat in ['p50','mean','p95']:
                before=groups[scenario+'-baseline']['stats'][key][stat]
                after=groups[scenario+'-candidate']['stats'][key][stat]
                result[key][stat]={'before':before,'after':after,'absolute_delta':after-before,'relative_percent':100*(after/before-1)}
        deltas[scenario]=result
    with (a.output/'generations.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(all_rows[0]),lineterminator="\n");writer.writeheader();writer.writerows(all_rows)
    metadata=json.loads((a.evidence/'campaign.json').read_text())
    summary={'base':metadata['released_base'],'backing':metadata['backing'],'probe_sha256':metadata['probe_sha256'],'probe_source_sha256':metadata['probe_source_sha256'],'candidate_provenance_sha256':metadata['candidate_provenance_sha256'],'groups':groups,'deltas':deltas,'method':'20 fresh parent processes per mode, alternating order; one sequential 20-generation process per mode; 1000-row fixture and 50 CRUD loops / 200 statements; no forced GC, cache flush or excluded complete trials; p95 nearest rank','phases':[{k:v for k,v in row.items() if k!='command'} for row in metadata['phases']]}
    (a.output/'measurements.json').write_text(json.dumps(summary,indent=2)+'\n')
    for mode in ['baseline','candidate']:
        rows=read(a.evidence/('profile-'+mode+'.log'))
        (a.output/('profile-'+mode+'.json')).write_text(json.dumps(rows,indent=2)+'\n')
        (a.output/('profile-top-'+mode+'.txt')).write_text((a.evidence/('profile-top-'+mode+'.log')).read_text())
    for metric in ['start_sql_ms','start_fixture_ms','crud_ms','start_sql_cpu_s','start_fixture_cpu_s','crud_cpu_s','total_cpu_s']:
        print(metric,deltas['fresh'][metric]['p50'])

if __name__=='__main__':main()
