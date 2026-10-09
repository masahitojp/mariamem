"""Serial orchestration: correctness first, exact release comparison second."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline-root', type=Path, required=True)
    parser.add_argument('--baseline-bench', required=True)
    parser.add_argument('--candidate-bench', required=True)
    parser.add_argument('--baseline-host', required=True)
    parser.add_argument('--candidate-host', required=True)
    parser.add_argument('--helper', required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--trials', type=int, default=3)
    parser.add_argument('--forks', type=int, default=16)
    parser.add_argument('--correctness-evidence', type=Path, required=True)
    parser.add_argument('--candidate-sha', required=True)
    args = parser.parse_args()
    gate=json.loads(args.correctness_evidence.read_text())
    if gate.get('result')!='PASS' or gate.get('candidate_sha')!=args.candidate_sha:
        parser.error('correctness gate is not PASS for this exact candidate')
    if args.trials<3 or args.forks<1:
        parser.error('3+ trials and positive forks required')
    args.out.mkdir(parents=True,exist_ok=True)
    args.scratch.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parents[2]
    variants={'baseline':(args.baseline_bench,args.baseline_host,args.baseline_root/'python'),
              'candidate':(args.candidate_bench,args.candidate_host,root/'python')}
    cases=[('fdscale',0,1,'read',64)]
    cases += [('serial',size,1,'read',1) for size in (0,10,100)]
    cases += [('capture',size,1,'read',1) for size in (0,10,100)]
    cases += [('crud',0,1,'crud',1),('application',0,1,'app-connections',1),
              ('parallel',10,4,'app-connections',1)]
    # Files, not payload bytes, determine retained-FD cost. Separate resource
    # phase holds 1/4/16 snapshots of a normal 64-table InnoDB baseline.
    commands=[]
    def run(argv,env=None):
        commands.append([str(arg) for arg in argv])
        (args.out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
        subprocess.run(argv,check=True,env=env)
    for case,size,workers,workload,tables in cases:
        external=args.scratch/f'external-{case}-{size}'
        trials=1 if case=='fdscale' else args.trials
        try:
            for trial in range(0 if case=='capture' else trials):
                order=('baseline','candidate') if trial%2==0 else ('candidate','baseline')
                for label in order:
                    run([variants[label][0],'-payload-mib',str(size),'-forks',str(args.forks),
                         '-workers',str(workers),'-workload',workload,'-tables',str(tables),
                         '-fd-snapshots','16' if case=='fdscale' else '0',
                         '-helper',args.helper,'-label',label,'-out',
                         str(args.out/f'go-{case}-{size}-{trial}-{label}.json')])
            # Both import variants see the same exact release-produced artifact.
            run([args.baseline_bench,'-payload-mib',str(size),'-forks','1','-tables',str(tables),
                 '-export',str(external),'-label','input-producer','-out',
                 str(args.out/f'input-{case}-{size}.json')])
            (args.out/f'manifest-{case}-{size}.json').write_bytes((external/'manifest.json').read_bytes())
            manifest=json.loads((external/'manifest.json').read_text())
            files=[entry for entry in manifest['entries'].values() if entry['kind']=='file']
            for path in args.out.glob(f'go-{case}-{size}-*.json'):
                data=json.loads(path.read_text())
                data.update(prepared_files=len(files),prepared_bytes=sum(entry['bytes'] for entry in files),
                            prepared_counts_source=f'manifest-{case}-{size}.json')
                path.write_text(json.dumps(data,indent=2)+'\n')
            for trial in range(trials):
                order=('baseline','candidate') if trial%2==0 else ('candidate','baseline')
                for label in order:
                    env=dict(os.environ,PYTHONPATH=str(variants[label][2]))
                    destination=args.scratch/f'capture-{size}-{trial}-{label}'
                    extra=['--capture','--capture-destination',str(destination)] if case=='capture' else []
                    run([sys.executable,str(Path(__file__).with_name('import_measure.py')),
                         '--artifact',str(external),'--host',variants[label][1],'--label',label,
                         '--helper',args.helper,'--forks',str(args.forks),'--workers',str(workers),
                         '--workload',workload,'--tables',str(tables),'--fd-snapshots','16' if case=='fdscale' else '0',
                         '--out',str(args.out/f'import-{case}-{size}-{trial}-{label}.json'),*extra],env)
                    if destination.exists():
                        shutil.rmtree(destination)
            if case=='fdscale':
                docs=[json.loads(path.read_text()) for path in args.out.glob('*-fdscale-0-0-*.json')]
                (args.out/'fd-resource-gate.json').write_text(json.dumps(dict(result='PASS',
                    candidate_sha=args.candidate_sha,checks='single 64-table baseline acquired; multiple-handle limits recorded',
                    scaling=docs),indent=2)+'\n')
        finally:
            if external.exists():
                shutil.rmtree(external)
    run([sys.executable,str(Path(__file__).with_name('summarize.py')),
         '--input',str(args.out),'--out',str(args.out/'reduced'),'--trials',str(args.trials),
         '--forks',str(args.forks)])


if __name__=='__main__':
    main()
