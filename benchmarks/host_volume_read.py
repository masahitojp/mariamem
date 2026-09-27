#!/usr/bin/env python3
"""Read-only experimental source probe; no destination copy or runtime rebuild."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from common import digest


def probe_source():
    text = (ROOT / 'guest/experimental.patch').read_text()
    section = text.split('+++ b/wasm/host_volume_probe.inc\n', 1)[1].splitlines()[1:]
    if not section or any(not line.startswith('+') for line in section):
        raise ValueError('experimental read-probe source patch drift')
    return '\n'.join(line[1:] for line in section) + '\n'


def snapshot_identity(path):
    begin = time.monotonic()
    manifest = json.loads((path / 'manifest.json').read_text())
    if manifest['version'] != 1:
        raise ValueError('snapshot format mismatch')
    expected = manifest['entries']
    files = {}
    seen = set()
    data = path / 'data'
    # Go filepath.WalkDir includes the root itself as the '.' directory entry.
    for p in [data, *sorted(data.rglob('*'))]:
        relative = p.relative_to(path / 'data').as_posix()
        if p.is_symlink() or any(c in relative for c in '\n\r\t"\\'):
            raise ValueError('unsafe snapshot path')
        seen.add(relative)
        if relative not in expected:
            raise ValueError('snapshot inventory mismatch: unexpected entry '+relative)
        item = expected[relative]
        if p.is_file():
            if item['kind'] != 'file' or p.stat().st_size != item['bytes'] or digest(p) != item['sha256']:
                raise ValueError('snapshot integrity mismatch: '+relative)
            files[relative] = {'bytes': item['bytes'], 'sha256': item['sha256']}
        elif not p.is_dir() or item['kind'] != 'directory':
            raise ValueError('snapshot entry type mismatch')
    if seen != set(expected):
        raise ValueError(f'snapshot inventory mismatch: missing={sorted(set(expected)-seen)}, unexpected={sorted(seen-set(expected))}')
    return {'manifest_sha256': digest(path / 'manifest.json'), 'files': files,
            'verification_seconds': time.monotonic()-begin}


def read_report(stdout, identity, expected_checksums=None, expected_mode=None):
    rows = [json.loads(line) for line in stdout.splitlines() if line]
    if not rows or rows[-1].get('completed') is not True or rows[-1].get('destination_writes') != 0 or rows[-1].get('chunk_bytes') != 65536:
        raise ValueError('read-only completion evidence missing')
    if expected_mode and rows[-1].get('mode') != expected_mode:
        raise ValueError('read-only mode mismatch')
    files = {row['file']: row for row in rows[:-1]}
    if len(files) != len(rows)-1 or set(files) != set(identity['files']):
        raise ValueError('read-only inventory mismatch')
    for name, row in files.items():
        if row['bytes'] != identity['files'][name]['bytes'] or row['read_calls'] < 1:
            raise ValueError('read byte reconciliation failed')
        if expected_checksums and row['checksum_fnv1a64'] != expected_checksums[name]:
            raise ValueError('read-content checksum mismatch: '+name)
    return {'files': files, 'total_bytes': sum(row['bytes'] for row in files.values()),
            'total_read_calls': sum(row['read_calls'] for row in files.values()),
            'read_wall_ns': sum(row['read_wall_ns'] for row in files.values()),
            'read_process_cpu_ns': None if any(row['read_process_cpu_ns'] is None for row in files.values()) else sum(row['read_process_cpu_ns'] for row in files.values()),
            'read_thread_cpu_ns': None if any(row['read_thread_cpu_ns'] is None for row in files.values()) else sum(row['read_thread_cpu_ns'] for row in files.values()),
            'checksum_wall_ns': sum(row['checksum_wall_ns'] for row in files.values()),
            'probe_wall_ns': rows[-1]['probe_wall_ns']}


def percentile(values, p):
    values = sorted(x for x in values if x is not None)
    if not values:
        return None
    index = (len(values)-1)*p; low = int(index)
    return values[low]+(values[min(low+1,len(values)-1)]-values[low])*(index-low)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-dir', type=Path, required=True)
    parser.add_argument('--runs', type=int, default=20)
    parser.add_argument('--warmup', type=int, default=2)
    parser.add_argument('--json', type=Path, required=True)
    args = parser.parse_args()
    if args.runs<1 or args.warmup<0:
        parser.error('invalid sample counts')
    native=args.native_dir.resolve(); output=args.json.resolve(); output.parent.mkdir(parents=True,exist_ok=True)
    report={'completed':False,'baseline_commit':'8b44e9db569c0ea04e45ae6c60fc8ecf54b7b8ab',
            'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'environment':{'platform':platform.platform(),'architecture':platform.machine(),'cpu_count':os.cpu_count(),
                           'go':subprocess.check_output(['go','version'],text=True).strip(),'python':sys.version},
            'native_manifest':json.loads((native/'manifest.json').read_text()),
            'aot_provenance':json.loads((native/'provenance.json').read_text()),
            'settings':{'runs':args.runs,'warmup':args.warmup,'workers':[1,4,8],'rows':1000,'chunk_bytes':65536},
            'samples':[], 'notes':['Checksumming is outside each timed read; its cost is recorded, not free.',
             'Guest direct fd_read bypasses libc and is a diagnostic control, not a restore change.',
             'Native libc differs from guest libc; native speed is not an exact removable-latency estimate.',
             'Host process CPU includes startup, checksums and runtime worker threads; no per-thread service attribution claimed.',
             'Snapshots are SHA256 verified before and after each batch; FNV checks reconcile bytes consumed, not a cryptographic trust cache.']}
    def save(): output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        with tempfile.TemporaryDirectory(prefix='mariamem-host-volume-') as directory:
            work=Path(directory); source=work/'probe.c';source.write_text(probe_source())
            binary=work/'native-read';subprocess.run(['cc','-O2','-std=gnu11',str(source),'-o',str(binary)],check=True)
            snapshot=work/'snapshot';setup=time.monotonic()
            fixture=subprocess.run(['go','run','./benchmarks/hostvolumefixture',str(native),str(snapshot)],cwd=ROOT,capture_output=True,text=True,check=True,timeout=240)
            report['fixture_setup']={'wall_seconds':time.monotonic()-setup,'details':json.loads(fixture.stdout)}
            identity=snapshot_identity(snapshot);report['snapshot_identity']=identity
            # One explicitly recorded native full-content pass establishes the
            # consumed-byte checksum; SHA256 remains the mandatory trust check.
            reference=subprocess.run([str(binary),str(snapshot/'data'),'stdio'],capture_output=True,text=True,check=True)
            checked=read_report(reference.stdout,identity,expected_mode='stdio');report['reference_and_cache_warming']=checked
            expected={name:row['checksum_fnv1a64'] for name,row in checked['files'].items()}
            env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','WASMER_','WASIX_'))}
            def execute(condition,index):
                kind,mode=condition.split('-')
                home=work/f'wasmer-{condition}-{index}';home.mkdir()
                command=([str(binary),str(snapshot/'data'),mode] if kind=='native' else
                         [str(native/'wasmer-headless'),'run',str(native/'mariamem.wasmu'),'--no-tty','--volume',str(snapshot)+':/snapshot-in','--','--host-volume-'+mode])
                begin=time.monotonic()
                result=subprocess.run(command,env={**env,'WASMER_DIR':str(home)},capture_output=True,text=True,timeout=120)
                shutil.rmtree(home)
                if result.returncode:
                    raise RuntimeError(f'{condition} exit={result.returncode}: {result.stderr[-3000:]}')
                row=read_report(result.stdout,identity,expected,mode);row['process_lifecycle_wall_seconds']=time.monotonic()-begin
                return row
            conditions=['guest-stdio','guest-direct','native-stdio','native-direct']
            for workers in [1,4,8]:
                for run in range(args.warmup+args.runs):
                    # Rotate order within each paired round.
                    order=conditions[run%4:]+conditions[:run%4]
                    for condition in order:
                        before=snapshot_identity(snapshot);cpu0=resource.getrusage(resource.RUSAGE_CHILDREN);start=time.monotonic()
                        with ThreadPoolExecutor(max_workers=workers) as pool:
                            rows=list(pool.map(lambda i:execute(condition,i),range(workers)))
                        wall=time.monotonic()-start;cpu1=resource.getrusage(resource.RUSAGE_CHILDREN)
                        after=snapshot_identity(snapshot)
                        if before['manifest_sha256']!=identity['manifest_sha256'] or before['files']!=identity['files'] or after['files']!=identity['files'] or after['manifest_sha256']!=identity['manifest_sha256']:
                            raise ValueError('snapshot mutated during read-only probe')
                        report['samples'].append({'condition':condition,'workers':workers,'run':run,'phase':'warmup' if run<args.warmup else 'measurement',
                          'verification_before_seconds':before['verification_seconds'],'verification_after_seconds':after['verification_seconds'],
                          'batch_wall_seconds':wall,'host_child_cpu_seconds':cpu1.ru_utime+cpu1.ru_stime-cpu0.ru_utime-cpu0.ru_stime,'per_process':rows})
                        save()
            # A traced run is kept separate and never enters latency percentiles.
            if sys.platform=='linux':
                if not shutil.which('strace'):
                    raise RuntimeError('Ubuntu diagnostic requires strace; install it before this probe')
                traces=output.parent/'host-volume-traces';traces.mkdir(exist_ok=True)
                for condition in ['guest-stdio','guest-direct','native-stdio','native-direct']:
                    home=work/('trace-'+condition);home.mkdir()
                    kind,mode=condition.split('-')
                    command=([str(binary),str(snapshot/'data'),mode] if kind=='native' else [str(native/'wasmer-headless'),'run',str(native/'mariamem.wasmu'),'--no-tty','--volume',str(snapshot)+':/snapshot-in','--','--host-volume-'+mode])
                    trace=traces/(condition+'.log')
                    result=subprocess.run(['strace','-f','-T','-yy','-e','trace=read,readv,pread64,lseek,futex','-o',str(trace),*command],env={**env,'WASMER_DIR':str(home)},capture_output=True,text=True,timeout=180)
                    if result.returncode:raise RuntimeError('syscall trace failed: '+result.stderr[-1500:])
                    read_report(result.stdout,identity,expected,mode)
                report['syscall_traces']={'directory':str(traces),'diagnostic_only':True}
            report['summary']=[]
            for workers in [1,4,8]:
                for condition in conditions:
                    samples=[s for s in report['samples'] if s['workers']==workers and s['condition']==condition and s['phase']=='measurement']
                    rows=[r for s in samples for r in s['per_process']]
                    entry={'condition':condition,'workers':workers,'count':len(rows)}
                    for metric in ['read_wall_ns','read_process_cpu_ns','read_thread_cpu_ns','checksum_wall_ns','probe_wall_ns','process_lifecycle_wall_seconds']:
                        entry[metric]={'p50':percentile([r[metric] for r in rows],.5),'p95':percentile([r[metric] for r in rows],.95)}
                    report['summary'].append(entry)
            report['completed']=True
    except Exception as exc:
        report['error']=str(exc);save();raise
    finally: save()
    print(json.dumps({'completed':True,'result':str(output)}))

if __name__=='__main__':main()
