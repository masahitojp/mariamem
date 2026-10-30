"""Build candidate wheel and run installed Python / external-module Go acceptance."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]


def run(argv,**kwargs):
    print('+',' '.join(map(str,argv)),flush=True)
    return subprocess.run(list(map(str,argv)),check=True,text=True,**kwargs)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--expected-source-commit',required=True)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True)
    sys.path.insert(0,str(ROOT/'scripts'))
    from git_identity import require_commit
    require_commit(ROOT,args.expected_source_commit)
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==args.expected_source_commit
    from release_runtime import stage
    wheel, _ = stage(ROOT, args.expected_source_commit)
    venv=out/'venv';run([sys.executable,'-m','venv',venv])
    python=venv/'bin/python'
    run([python,'-m','pip','install','--no-index','--no-deps',wheel])
    # Use the already installed, pinned PyMySQL without any network or source SDK.
    import pymysql
    site=Path(subprocess.check_output([python,'-c','import sysconfig; print(sysconfig.get_paths()["purelib"])'],text=True).strip())
    shutil.copytree(Path(pymysql.__file__).parent,site/'pymysql')
    shutil.copy2(Path(__file__).with_name('installed_python.py'),out/'installed_python.py')
    env=os.environ.copy();env.pop('PYTHONPATH',None)
    with (out/'python.txt').open('w') as log:run([python,out/'installed_python.py'],cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT)
    consumer=out/'go-consumer';consumer.mkdir();shutil.copy2(Path(__file__).with_name('go_consumer')/'main.go',consumer/'main.go')
    (consumer/'go.mod').write_text('module example.com/live-consumer\n\ngo 1.26.0\n\nrequire github.com/masahitojp/mariamem v0.0.0\nreplace github.com/masahitojp/mariamem => '+ROOT.as_posix()+'\n')
    run(['go','mod','tidy'],cwd=consumer)
    with (out/'go.txt').open('w') as log:run(['go','run','.'],cwd=consumer,stdout=log,stderr=subprocess.STDOUT)
    py=json.loads((out/'python.txt').read_text().splitlines()[-1]);go=json.loads((out/'go.txt').read_text().splitlines()[-1])
    assert py['result']=='PASS_INSTALLED_PYTHON_LIVE' and str(site) in py['module']
    assert go['result']=='PASS_EXTERNAL_GO_LIVE'
    (out/'result.json').write_text(json.dumps(dict(result='PASS_INSTALLED_LIVE',source_commit=args.expected_source_commit,wheel_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),python=py,go=go),indent=2)+'\n')
    # These are recreatable consumer environments, not durable evidence.
    shutil.rmtree(venv);shutil.rmtree(consumer)
    return 0


if __name__=='__main__':raise SystemExit(main())
