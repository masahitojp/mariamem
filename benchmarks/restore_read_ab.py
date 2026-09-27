#!/usr/bin/env python3
"""Real import-only A/B; one fixture, alternating conditions, canonical Go batches."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import time

from host_volume_read import ROOT, digest, percentile, snapshot_identity


def run(command, **kwargs):
    result = subprocess.run([str(x) for x in command], capture_output=True, text=True, **kwargs)
    if result.returncode:
        raise RuntimeError(f'{command[0]} exit={result.returncode}: {result.stderr[-6000:]}\n{result.stdout[-2000:]}')
    return result


def inventory(data):
    result = {}
    for path in [data, *sorted(data.rglob('*'))]:
        name = path.relative_to(data).as_posix()
        if path.is_symlink():
            raise ValueError('restored symlink: '+name)
        if path.is_dir():
            result[name] = {'kind': 'directory'}
        elif path.is_file():
            result[name] = {'kind': 'file', 'bytes': path.stat().st_size, 'sha256': digest(path)}
        else:
            raise ValueError('restored special/missing file: '+name)
    return result


def validate_stats(row, mode, identity):
    stats = row['stage_timings']['host']['guest']['restore_copy']
    if (stats['mode'] != mode or stats['chunk_bytes'] != 65536 or
            stats['bytes'] != identity['data_bytes'] or stats['written_bytes'] != identity['data_bytes'] or
            stats['files'] != len(identity['file_bytes']) or stats['read_calls'] < stats['files']):
        raise ValueError('restore mode/inventory/byte reconciliation failed')
    return stats


def metrics(row):
    stats = row['stage_timings']['host']['guest']['restore_copy']
    values = {'fork_first_sql_ms': row['latency_seconds']*1000}
    for key in ['total_wall_ns', 'read_wall_ns', 'write_wall_ns', 'total_process_cpu_ns',
                'total_thread_cpu_ns', 'read_process_cpu_ns', 'read_thread_cpu_ns',
                'write_process_cpu_ns', 'write_thread_cpu_ns', 'guest_main_to_ready_process_cpu_ns']:
        values[key.removesuffix('_ns')+'_ms'] = None if stats[key] is None else stats[key]/1e6
    return values


def summarize(report):
    result = []
    for workers in [1, 4, 8]:
        groups = {}
        for mode in ['stdio', 'direct']:
            batches = [s for s in report['samples'] if s['phase']=='measurement' and s['workers']==workers and s['condition']==mode]
            groups[mode] = {s['run']:s for s in batches}
            rows = [metrics(row) for batch in batches for row in batch['per_db']]
            item = {'workers':workers, 'condition':mode, 'per_db_count':len(rows), 'metrics':{}}
            for key in rows[0]:
                values = [r[key] for r in rows]
                item['metrics'][key] = {'p50':percentile(values,.5), 'p95':percentile(values,.95), 'available_samples':sum(v is not None for v in values)}
            item['runner_batch_cpu_ms'] = {f'p{p}':percentile([s['runner_cpu_seconds']*1000 for s in batches],p/100) for p in [50,95]}
            result.append(item)
        paired = {'workers':workers, 'comparison':'stdio minus direct; same-round mean of per-DB observations', 'pairs':[]}
        if set(groups['stdio']) != set(groups['direct']):
            raise ValueError('missing paired condition')
        for index in sorted(groups['stdio']):
            pair = {'run':index}
            for key in metrics(groups['stdio'][index]['per_db'][0]):
                sides = [[metrics(r)[key] for r in groups[mode][index]['per_db']] for mode in ['stdio','direct']]
                pair[key] = None if any(v is None for side in sides for v in side) else sum(sides[0])/workers-sum(sides[1])/workers
            paired['pairs'].append(pair)
        paired['summary'] = {key:{f'p{p}':percentile([r[key] for r in paired['pairs']],p/100) for p in [50,95]} for key in paired['pairs'][0] if key!='run'}
        result.append(paired)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-dir',type=Path,required=True)
    parser.add_argument('--runs',type=int,default=20)
    parser.add_argument('--warmup',type=int,default=2)
    parser.add_argument('--json',type=Path,required=True)
    args = parser.parse_args()
    if args.runs<1 or args.warmup<0:
        parser.error('invalid sample counts')
    native=args.native_dir.resolve();output=args.json.resolve();output.parent.mkdir(parents=True,exist_ok=True)
    evidence={'completed':False,'source_commit':run(['git','rev-parse','HEAD'],cwd=ROOT).stdout.strip(),
              'environment':{'platform':platform.platform(),'architecture':platform.machine(),'cpu_count':os.cpu_count(),
                             'go':run(['go','version']).stdout.strip(),'python':platform.python_version()},
              'native_manifest':json.loads((native/'manifest.json').read_text()),
              'aot_provenance':json.loads((native/'provenance.json').read_text()),'correctness':{},
              'settings':{'runs':args.runs,'warmup':args.warmup,'workers':[1,4,8],'rows':1000,'chunk_bytes':65536},
              'notes':['Guest CPU from guest-main to ready excludes runtime pre-main, first SQL and shutdown.',
                       'Runner CPU covers canonical host/harness/driver/sampler/hold/cleanup; ps remains approximate.',
                       'Exact-content roundtrip runs separately, before measured A/B; no checksum in copy loop.',
                       '20 round pairs; per-worker arrival order is not stable, so parallel paired effects use batch means.',
                       'Decision requires analysis of paired latency, CPU and tails; a read-only saving is insufficient.']}
    def save():output.write_text(json.dumps(evidence,indent=2)+'\n')
    save()
    try:
        with tempfile.TemporaryDirectory(prefix='mariamem-restore-ab-') as directory:
            tmp=Path(directory);snapshot=tmp/'snapshot';start=time.monotonic()
            fixture=run(['go','run','./benchmarks/hostvolumefixture',native,snapshot],cwd=ROOT,timeout=240)
            source=snapshot_identity(snapshot);manifest=json.loads((snapshot/'manifest.json').read_text())
            evidence['correctness']['fixture_setup']={'seconds':time.monotonic()-start,'details':json.loads(fixture.stdout),'identity':source}
            for mode in ['stdio','direct']:
                transfer=tmp/mode;transfer.mkdir();home=tmp/('home-'+mode);home.mkdir();begin=time.monotonic()
                run([native/'wasmer-headless','run',native/'mariamem.wasmu','--no-tty',
                     '--volume',str(snapshot)+':/snapshot-in','--volume',str(transfer)+':/snapshot-out',
                     '--env','MARIAMEM_GUEST_TIMING=1','--env','MARIAMEM_EXPERIMENT_RESTORE='+mode,
                     '--env','MARIAMEM_EXPERIMENT_RESTORE_VERIFY=1','--','--restore-snapshot'],
                     env={**os.environ,'WASMER_DIR':str(home)},timeout=180)
                if inventory(transfer/'verified') != manifest['entries']:
                    raise ValueError(mode+' restored contents differ before MariaDB startup')
                trace=json.loads((transfer/'startup-timing.json').read_text())
                validate_stats({'stage_timings':{'host':{'guest':trace}}},mode,
                               {'data_bytes':sum(v['bytes'] for v in source['files'].values()),'file_bytes':source['files']})
                if snapshot_identity(snapshot)['files'] != source['files']:
                    raise ValueError('source changed during correctness run')
                evidence['correctness'][mode]={'PASS':True,'wall_seconds':time.monotonic()-begin,'timing':trace}
                save()
            binary=tmp/'isolation';raw=tmp/'raw.json'
            run(['go','build','-trimpath','-o',binary,'./benchmarks/goisolation'],cwd=ROOT)
            evidence['runner_sha256']=digest(binary)
            try:
                run([binary,'--native-dir',native,'--json',raw,'--restore-ab','--stage-timing','--guest-stage-timing',
                     '--runs',args.runs,'--warmup',args.warmup,'--workers','1,4,8','--rows','1000'],cwd=ROOT,timeout=2400)
            except Exception:
                if raw.is_file():
                    evidence['canonical_go']=json.loads(raw.read_text())
                save()
                raise
            measured=json.loads(raw.read_text())
            if not measured['completed']:
                raise ValueError('canonical Go A/B incomplete')
            if len(measured['samples']) != 6*(args.runs+args.warmup):
                raise ValueError('canonical Go A/B missing batches')
            for sample in measured['samples']:
                for row in sample['per_db']:
                    validate_stats(row,sample['condition'],sample['snapshot_inventory'])
            evidence['canonical_go']=measured
            evidence['summary']=summarize(measured)
            evidence['completed']=True
            evidence['decision']='pending evidence review; not production acceptance'
    except Exception as error:
        evidence['error']=str(error);save();raise
    finally:save()
    print(json.dumps({'completed':True,'result':str(output)}))

if __name__=='__main__':main()
