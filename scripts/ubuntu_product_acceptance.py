#!/usr/bin/env python3
"""Clean Ubuntu consumers of exact native/wheel bytes; no local source/runtime fallback."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

from common import ROOT, digest
from platform_acceptance import extract, isolated_env
from native_target import UBUNTU


def validate_inputs(archive, native_hash, wheel, wheel_hash, commit):
    import re
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('expected exact source commit')
    for path, expected in ((archive,native_hash),(wheel,wheel_hash)):
        if not re.fullmatch('[0-9a-f]{64}', expected) or digest(path)!=expected:
            raise ValueError('acceptance input hash mismatch: '+path.name)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--native-sha256',required=True)
    parser.add_argument('--wheel',type=Path,required=True)
    parser.add_argument('--wheel-sha256',required=True)
    parser.add_argument('--commit',required=True)
    args=parser.parse_args()
    output=ROOT/'build/release/ubuntu-product-acceptance.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    report={'result':'FAIL','source_commit':args.commit,'stage':'inputs','steps':{},'native_sha256':args.native_sha256,'wheel_sha256':args.wheel_sha256}
    def execute(name,argv,cwd=None,env=None):
        report['stage']=name
        result=subprocess.run([str(a) for a in argv],cwd=cwd,env=env,text=True,capture_output=True,timeout=900)
        (output.parent/(name+'.log')).write_text(result.stdout+result.stderr)
        if result.returncode:
            raise ValueError(f'{name} failed; see {name}.log: '+result.stderr[-1500:])
        report['steps'][name]='PASS'
    try:
        validate_inputs(args.archive,args.native_sha256,args.wheel,args.wheel_sha256,args.commit)
        os_release=platform.freedesktop_os_release()
        if platform.system()!='Linux' or platform.machine()!='x86_64' or os_release.get('ID')!='ubuntu' or os_release.get('VERSION_ID')!='24.04':
            raise ValueError('clean product acceptance requires Ubuntu 24.04 x86_64')
        report['environment']={'os_release':os_release,'architecture':platform.machine(),'python':sys.version}
        execute('native_consumer',[sys.executable,ROOT/'scripts/platform_acceptance.py','--target',UBUNTU,'--archive',args.archive,'--sha256',args.native_sha256,'--module',args.commit,'--expected-commit',args.commit,'--evidence',output.parent/'ci-native-acceptance.json'])
        with tempfile.TemporaryDirectory(prefix='mariamem-ubuntu-consumer-') as temporary:
            work=Path(temporary)
            env=isolated_env(work)
            env={k:v for k,v in env.items() if not k.startswith(('PYTHON','PYTEST'))}
            native=extract(args.archive,work/'native',UBUNTU)
            go=work/'go';go.mkdir()
            shutil.copy(ROOT/'scripts/ubuntu_acceptance/lifecycle.go',go/'main.go')
            execute('go_init',['go','mod','init','mariamem-ubuntu-consumer'],go,env)
            execute('go_fetch',['go','get','github.com/masahitojp/mariamem@'+args.commit],go,env)
            execute('go_tidy',['go','mod','tidy'],go,env)
            execute('go_lifecycle',['go','run','.',native],go,env)
            venv=work/'venv'
            execute('venv',[sys.executable,'-m','venv',venv],work,env)
            python=venv/'bin/python'
            execute('wheel_install',[python,'-m','pip','install',str(args.wheel.resolve())+'[test]'],work,env)
            execute('installed_wheel',[python,ROOT/'tests/verify_alpha.py'],work,env)
            shutil.copy(ROOT/'tests/consumer/test_ubuntu.py',work/'test_ubuntu.py')
            execute('python_lifecycle',[python,'-m','pytest','-q',work/'test_ubuntu.py'],work,env)
        report['result']='PASS';report['stage']='complete'
    except (ValueError,OSError,subprocess.TimeoutExpired) as exc:
        report['error']=str(exc)
    finally:
        output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return 0 if report['result']=='PASS' else 1


if __name__=='__main__':
    raise SystemExit(main())
