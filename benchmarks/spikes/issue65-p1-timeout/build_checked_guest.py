#!/usr/bin/env python3
"""Run the unchanged dev builder,checking actual prepared seams before source disposal."""
import argparse,importlib.util,json,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);a=p.parse_args();w=a.workspace.resolve();repo=w/'worktree'
    sys.path.insert(0,str(repo/'scripts'))
    spec=importlib.util.spec_from_file_location('fixed_dev_builder',repo/'scripts/build_generated_guest.py');builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    original=builder.observed_run;checked=[]
    def run(*args,**kwargs):
        result=original(*args,**kwargs)
        if kwargs.get('phase')=='guest:prepare:0':
            if checked:raise ValueError('duplicate prepared source check')
            output=w/'temp/source-seams'
            subprocess.run([sys.executable,HERE/'check_source.py','--source',repo/'build/source/sql/sql_prepare.cc','--output',output],check=True)
            shutil.copy2(output/'result.json',w/'evidence/source-seams.json')
            controls=w/'temp/controller-controls'
            subprocess.run([sys.executable,HERE/'check_timeout.py','--source',repo/'build/source/wasm/issue65_control.cc','--header',repo/'build/source/wasm/issue65_deadline.h','--output',controls],check=True)
            shutil.copy2(controls/'result.json',w/'evidence/controller-controls.json');checked.append(True)
        return result
    builder.observed_run=run
    sys.argv=[str(repo/'scripts/build_generated_guest.py'),'--development-output',str(w/'temp/artifact')]
    builder.main()
    if checked!=[True]:raise ValueError('prepared source was not checked')
if __name__=='__main__':main()
