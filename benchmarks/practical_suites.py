#!/usr/bin/env python3
"""Repeated isolated-test workflows on the fixed macOS arm64 reference."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
MODES=('mariamem-fresh','mariamem-prepared','testcontainers-fresh','testcontainers-schema-reset')

def percentile(values,p):
    values=sorted(values);x=(len(values)-1)*p;i=int(x)
    return values[i]+(values[min(i+1,len(values)-1)]-values[i])*(x-i)

def summarize(report):
    if not report['completed']:
        raise ValueError('incomplete run; failed suites cannot be discarded')
    result=[]
    for n in report['counts']:
        for mode in MODES:
            suites=[s for s in report['suites'] if s['phase']=='measurement' and s['mode']==mode and s['tests']==n]
            if {s['round'] for s in suites}!=set(range(report['runs'])) or any(s.get('exit_code',0) for s in suites):raise ValueError('missing/failed suite round')
            rows=[s['report'] for s in suites]
            if len(rows)!=report['runs'] or any(not s['completed'] or len(s['samples'])!=n for s in rows):
                raise ValueError('missing suite/test')
            versions={s['server_version'] for s in rows}
            if len(versions)!=1:raise ValueError('server version changed')
            row={'tests':n,'mode':mode,'suite_trials':len(rows),'server_version':next(iter(versions))}
            for key in ('suite_wall_seconds','setup_wall_seconds','runner_cpu_seconds','waited_children_cpu_seconds'):
                values=[r[key] for r in rows];row[key]={'min':min(values),'p50':percentile(values,.5),'p95':percentile(values,.95),'max':max(values)}
            for key in ('fixture_ready_seconds','startup_first_sql_seconds','migration_fixture_seconds','schema_reset_migration_fixture_seconds','cleanup_seconds'):
                values=[s[key] for r in rows for s in r['samples'] if key in s]
                row[key]=None if not values else {'count':len(values),'p50':percentile(values,.5),'p95':percentile(values,.95)}
            row['resource_samples']=[s['ready_cost'] for r in rows for s in r['samples'] if 'ready_cost' in s]
            if mode.startswith('testcontainers'):
                values=[]
                for r in rows:
                    counters=[s['ready_cost'].get('cpu_seconds') for s in r['samples'] if 'ready_cost' in s]
                    if counters and all(x is not None for x in counters):
                        values.append(sum(counters) if mode=='testcontainers-fresh' else counters[-1])
                row['observed_container_cpu_seconds']=None if not values else {'p50':percentile(values,.5),'p95':percentile(values,.95)}
            result.append(row)
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-dir',type=Path,required=True)
    parser.add_argument('--runs',type=int,default=3)
    parser.add_argument('--counts',type=int,nargs='+',default=[10,50,100])
    parser.add_argument('--json',type=Path,default=ROOT/'benchmarks/results/practical-suites.json')
    args=parser.parse_args()
    if platform.system()!='Darwin' or platform.machine()!='arm64':parser.error('fixed-reference comparison requires macOS arm64; no emulation')
    if args.runs<3 or any(n<1 for n in args.counts) or len(set(args.counts))!=len(args.counts):parser.error('3+ suite repeats and unique positive counts required')
    output=args.json.resolve();output.parent.mkdir(parents=True,exist_ok=True)
    if output.is_relative_to(ROOT) and not output.is_relative_to(ROOT/'benchmarks/results'):parser.error('checkout output must be ignored benchmarks/results')
    capture=lambda command:subprocess.check_output(command,text=True,cwd=ROOT).strip()
    inputs=json.loads((ROOT/'benchmarks/practical-suite-inputs.json').read_text());native=args.native_dir.resolve()
    manifest=json.loads((native/'manifest.json').read_text())
    for name,digest in manifest['sha256'].items():
        if hashlib.sha256((native/name).read_bytes()).hexdigest()!=digest:raise ValueError('native artifact mismatch: '+name)
    subprocess.run(['docker','pull','--platform','linux/arm64',inputs['image']],check=True)
    image=json.loads(capture(['docker','image','inspect',inputs['image']]))[0]
    if image['Architecture']!='arm64' or not any(x.endswith('@'+inputs['image'].split('@')[1]) for x in image['RepoDigests']):raise ValueError('image platform/digest mismatch')
    info=json.loads(capture(['docker','info','--format','{{json .}}']))
    endpoint=capture(['docker','context','inspect','--format','{{.Endpoints.docker.Host}}'])
    if not endpoint.startswith('unix://'):raise ValueError('local Docker unix context required')
    env=os.environ.copy();env['DOCKER_HOST']=endpoint;env['GOTOOLCHAIN']='go1.26.8'
    for k in ('MARIAMEM_TIMING_DIR','MARIAMEM_INIT_DIAGNOSTICS','MARIAMEM_MEMORY_DIAGNOSTICS'):env.pop(k,None)
    binary=ROOT/'build/bench/practical-suite';binary.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['go','build','-mod=readonly','-trimpath','-o',str(binary),'.'],cwd=ROOT/'benchmarks/competitive',env=env,check=True)
    report={'schema_version':1,'completed':False,'source_commit':capture(['git','rev-parse','HEAD']),
            'source_dirty':bool(capture(['git','status','--porcelain'])), 'runs':args.runs,'counts':args.counts,'inputs':inputs,
            'native_manifest':manifest,'runner_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
            'environment':{'platform':platform.platform(),'model':capture(['sysctl','-n','hw.model']),
                'cpu':capture(['sysctl','-n','machdep.cpu.brand_string']),'ram_bytes':int(capture(['sysctl','-n','hw.memsize'])),
                'os_version':capture(['sw_vers','-productVersion']),'os_build':capture(['sw_vers','-buildVersion']),
                'measured_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'docker_version':capture(['docker','version']),
                'docker_info':{k:info[k] for k in ('ServerVersion','NCPU','MemTotal','KernelVersion','Driver','OperatingSystem','Architecture','ContainersRunning')},
                'python':platform.python_version()},'suites':[]}
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    try:
        for phase,rounds,counts in [('warmup',1,[1]),('measurement',args.runs,args.counts)]:
            for n in counts:
                for r in range(rounds):
                    order=MODES[r%len(MODES):]+MODES[:r%len(MODES)]
                    for mode in order:
                        raw=output.with_name(f'{output.stem}-{phase}-{n}-{r}-{mode}.json');log=raw.with_suffix('.log')
                        begun=time.monotonic()
                        with log.open('w') as f:
                            p=subprocess.run([str(binary),'--suite-mode',mode,'--suite-count',str(n),'--native-dir',str(native),'--image',inputs['image'],'--json',str(raw)],cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT)
                        row={'phase':phase,'tests':n,'round':r,'mode':mode,'exit_code':p.returncode,'supervisor_wall_seconds':time.monotonic()-begun,'report':json.loads(raw.read_text()) if raw.exists() else None}
                        report['suites'].append(row);save()
                        if row['report'] and row['report'].get('completed'):
                            ids=sorted({s['container_id'] for s in row['report']['samples'] if s.get('container_id')})
                            if ids:
                                check=subprocess.run(['docker','inspect',*ids],capture_output=True,text=True)
                                absent=check.returncode!=0 and json.loads(check.stdout or '[]')==[]
                                row['all_test_container_ids_removed']=absent
                                if not absent:raise RuntimeError('owned DB container remains after suite')
                                save()
                        print(phase,n,r,mode,'exit',p.returncode,flush=True)
                        if p.returncode or not row['report'] or not row['report']['completed']:raise RuntimeError('failed suite: '+str(log))
        report['completed']=True;report['summary']=summarize(report)
    except Exception as e:
        report['error']=str(e);raise
    finally:save()

if __name__=='__main__':main()
