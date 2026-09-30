#!/usr/bin/env python3
"""Run isolated wasm2go feature reductions; failures are retained as evidence."""
import argparse
import json
from pathlib import Path
import subprocess
import time


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--converter',type=Path,required=True)
    p.add_argument('--wasm-tools',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--case',nargs='+',help='run only selected fixture stems')
    p.add_argument('--host-shims',action='store_true',help='also run explicit, limited host adapters')
    a=p.parse_args();converter=a.converter.resolve();tools=a.wasm_tools.resolve()
    output=a.output_dir.resolve();output.mkdir(parents=True,exist_ok=True);records=[]
    # Failed conversions can leave empty .go files. Keep every result outside
    # the product module, including cases that never reach a Go build.
    (output/'go.mod').write_text('module example.com/mariamem-spike-results\n\ngo 1.26.0\n')
    def run(label,cmd,cwd=None):
        start=time.monotonic()
        r=subprocess.run([str(x) for x in cmd],cwd=cwd,capture_output=True,text=True,timeout=120)
        row=dict(label=label,command=[str(x) for x in cmd],seconds=time.monotonic()-start,
                 exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr)
        records.append(row)
        (output/'results.json').write_text(json.dumps(records,indent=2)+'\n')
        print(label,r.returncode,r.stderr[:100],flush=True)
        return r
    for f in sorted(Path(__file__).parent.glob('*.wat')):
        name=f.stem
        if a.case and name not in a.case:continue
        directory=output/name
        if directory.exists():p.error('use an unused output directory to avoid stale results')
        directory.mkdir()
        (directory/'go.mod').write_text('module example.com/spike\n\ngo 1.26.0\n')
        wasm=directory/'input.wasm';generated=directory/'generated';generated.mkdir(exist_ok=True)
        run(name+'/parse',[tools,'parse',f,'-o',wasm])
        valid=run(name+'/validate',[tools,'validate','--features=all',wasm])
        if valid.returncode:raise ValueError('invalid reduction '+name)
        result=run(name+'/convert',[converter,'-pure','-i',wasm,'-out-dir',generated,
                                  '-o',generated/'module.go','-pkg','generated','-import','example.com/spike/generated'])
        if result.returncode:continue
        body=(generated/'module.go').read_text()
        ctor='generated.New()'
        if 'func New(' in body and 'func New()' not in body:
            # Custom WASIX/imported-memory interfaces intentionally fail fast.
            ctor='generated.New(nil)'
        main='package main\nimport("fmt"; "example.com/spike/generated")\nfunc main(){fmt.Println('+ctor+'.Run())}\n'
        (directory/'main.go').write_text(main)
        result=run(name+'/build',['go','build','-trimpath','-o',directory/'probe','.'],cwd=directory)
        if result.returncode==0:
            run(name+'/execute',[directory/'probe'])
        templates={'wasi-filesystem':'memfs-driver.go.txt','wasix-futex':'futex-shim.go.txt','thread-exit':'thread-exit-shim.go.txt','wasix-path-open':'path-open-shim.go.txt'}
        if a.host_shims and name in templates:
            if name=='thread-exit':
                (generated/'spike_wait.go').write_text((Path(__file__).parent/'await-threads.go.txt').read_text())
            (directory/'main.go').write_text((Path(__file__).parent/templates[name]).read_text())
            built=run(name+'/shim-build',['go','build','-trimpath','-o',directory/'probe-shim','.'],cwd=directory)
            if built.returncode==0:run(name+'/shim-execute',[directory/'probe-shim'])
        records.append(dict(label=name+'/sizes',generated_bytes=sum(x.stat().st_size for x in generated.rglob('*') if x.is_file()),
                            binary_bytes=(directory/'probe').stat().st_size if (directory/'probe').exists() else None))
    (output/'results.json').write_text(json.dumps(records,indent=2)+'\n')

if __name__=='__main__':main()
