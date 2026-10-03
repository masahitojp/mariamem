#!/usr/bin/env python3
"""Independent-process fresh vs prepared suites; caller serializes heavy work."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
BASE = '39537e9bb2fbbc28315e1ff672960ad734a9e399'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def percentile(values, p):
    ordered = sorted(values)
    index = (len(ordered)-1)*p
    low = int(index); high = min(low+1, len(ordered)-1)
    return ordered[low]+(ordered[high]-ordered[low])*(index-low)
def distribution(values):
    return dict(n=len(values), min=min(values), mean=sum(values)/len(values),
                p50=percentile(values, .5), p95=percentile(values, .95), max=max(values))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--rounds', type=int, default=3)
    parser.add_argument('--summary', type=Path, required=True)
    parser.add_argument('--samples', type=Path, required=True)
    args = parser.parse_args()
    if args.rounds < 3: parser.error('at least three diagnostic rounds')
    work = args.work.resolve(); work.mkdir(parents=True, exist_ok=True)
    if work.is_relative_to(ROOT): parser.error('raw/build work must be outside checkout')
    env = dict(os.environ, GOTOOLCHAIN='go1.26.8', GOWORK='off')
    for key in ('MARIAMEM_NATIVE_DIR', 'MARIAMEM_RUNTIME', 'MARIAMEM_TIMING_DIR',
                'MARIAMEM_INIT_DIAGNOSTICS', 'MARIAMEM_MEMORY_DIAGNOSTICS'):
        env.pop(key, None)
    binary = work/'fixture-crossover'
    compile_start = time.monotonic()
    subprocess.run(['go','build','-o',str(binary),'.'], cwd=ROOT/'benchmarks/fixturecrossover',env=env,check=True)
    compile_seconds = time.monotonic()-compile_start
    report = dict(schema_version=1, base_sha=BASE, source_sha=subprocess.check_output(
                  ['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                  runtime='direct-linked generated-Go', platform=platform.platform(),
                  measured_at_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                  arch=platform.machine(), go=subprocess.check_output(['go','version'],env=env,text=True).strip(),
                  fixture_sources=['benchmarks/goisolation/main.go','tests/consumer/gorm/dogfood_test.go'],
                  fixture_source_sha256={name:sha(ROOT/name) for name in ('benchmarks/goisolation/main.go','tests/consumer/gorm/dogfood_test.go')},
                  harness_sha256={name:sha(ROOT/'benchmarks/fixturecrossover'/name) for name in ('main.go','run.py','go.mod','go.sum')},
                  binary_sha256=sha(binary), generated_provenance_sha256=sha(ROOT/'internal/generatedgo/provenance.json'),
                  guest_sha256=json.loads((ROOT/'internal/generatedgo/provenance.json').read_text())['guest_sha256'],
                  compile_seconds=compile_seconds, settings=dict(rounds=args.rounds,counts=[10,50,100],warmup_tests=1,
                  per_suite_timeout_seconds=900, no_slow_samples_removed=True, forced_gc=False), suites=[])
    all_rows=[]
    for scenario in ('fixture-1000','gorm-user-address'):
        for mode in ('fresh','fork'):
            output = work/f'warmup-{scenario}-{mode}.json'
            subprocess.run([str(binary),'--scenario',scenario,'--mode',mode,'--tests','1','--json',str(output)],cwd=ROOT,env=env,check=True,timeout=900)
        for count in (10,50,100):
            for trial in range(args.rounds):
                modes=('fresh','fork') if (trial+count//10)%2==0 else ('fork','fresh')
                for mode in modes:
                    output=work/f'{scenario}-{mode}-{count}-{trial}.json'
                    subprocess.run([str(binary),'--scenario',scenario,'--mode',mode,'--tests',str(count),'--json',str(output)],cwd=ROOT,env=env,check=True,timeout=900)
                    result=json.loads(output.read_text())
                    if not result['completed'] or len(result['samples'])!=count: raise RuntimeError('incomplete suite')
                    samples=result.pop('samples'); result.update(trial=trial,raw_file=output.name,raw_sha256=sha(output))
                    result['case_summary']={key:distribution([s[key] for s in samples]) for key in ('entry_ms','prepare_ms','ready_ms','work_ms','close_ms','total_ms')}
                    result['ready_ge_500_ms']=sum(s['ready_ms']>=500 for s in samples)
                    result['ready_ge_900_ms']=sum(s['ready_ms']>=900 for s in samples)
                    report['suites'].append(result)
                    for sample in samples: all_rows.append(dict(scenario=scenario,mode=mode,tests=count,trial=trial,**sample))
                    args.summary.parent.mkdir(parents=True,exist_ok=True)
                    args.summary.write_text(json.dumps(report,indent=2)+'\n')
    args.samples.parent.mkdir(parents=True,exist_ok=True)
    with args.samples.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(all_rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(all_rows)
    report['samples_csv_sha256']=sha(args.samples)
    report['completed']=True
    args.summary.write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__': main()
