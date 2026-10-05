#!/usr/bin/env python3
"""External normal Go module and installed host-only wheel acceptance.

Candidate mode uses an exact-source private module proxy, not replace or a native
bundle. Published mode binds the public tag to the accepted source commit.
The known full-generated-guest race limitation is not suppressed or a gate here.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from common import ROOT, digest
from consumer_module import MODULE, prepare_proxy
from generated_release import CONTRACT, STEPS, checkout, require, source_inventory, verify_wheel, version, write
from platform_acceptance import isolated_env, bind_remote_origin
from release_consumer_smoke import environment


def harness_inventory(root):
    paths=[root/'scripts/generated_release_acceptance.py', root/'scripts/consumer_module.py',
           root/'scripts/platform_acceptance.py',root/'scripts/release_consumer_smoke.py',root/'tests/verify_alpha.py',
           *sorted((root/'tests/godefault').glob('*.go')),
           root/'tests/consumer/test_database.py',root/'tests/consumer/test_generated_platform.py',
           root/'tests/consumer/test_sqlalchemy_dogfood.py',
           *sorted((root/'tests/consumer/gorm').glob('*'))]
    return {p.relative_to(root).as_posix():digest(p) for p in paths if p.is_file()}


def accept(root, commit, platform, output, mode='candidate', wheel=None, go_build_jobs=None):
    root=root.resolve(); output=output.resolve()
    require(not output.exists(),'refuse stale acceptance evidence')
    require(mode in ('candidate','published'),'unknown acceptance mode')
    if mode=='candidate': checkout(root,commit)
    selected,record=verify_wheel(root,platform,commit)
    if wheel is not None:
        require(wheel.resolve()==selected.resolve(),'selected wheel differs from frozen metadata')
    metadata=version(root); report={'contract':CONTRACT,'result':'FAIL','source_commit':commit,'mode':mode,
             'platform':platform,'python_version':metadata['PYTHON_VERSION'],'module_version':metadata['GIT_TAG'],
             'wheel_sha256':record['sha256'],'go_source_sha256':source_inventory(root),
             'harness_sha256':harness_inventory(root),'steps':{},'runtime_overrides':False,
             'outside_checkout':True,'environment':environment(platform)}
    log=output.with_suffix('.log'); log.parent.mkdir(parents=True,exist_ok=True)
    def run(command,cwd,env):
        with log.open('a') as stream:
            stream.write(json.dumps(list(map(str,command)))+'\n'); stream.flush()
            subprocess.run(list(map(str,command)),cwd=cwd,env=env,stdout=stream,
                           stderr=subprocess.STDOUT,check=True,timeout=1200)
    try:
        with tempfile.TemporaryDirectory(prefix='mariamem-v04-acceptance-') as temporary:
            work=Path(temporary).resolve(); require(not work.is_relative_to(root),'consumer must be external')
            env=isolated_env(work)
            env={k:v for k,v in env.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_','PYTHON','PYTEST','DOGFOOD_'))}
            require(go_build_jobs is None or go_build_jobs > 0,'Go build jobs must be positive')
            env.update(GOTOOLCHAIN='go1.26.8',GOWORK='off',GOENV='off',GOFLAGS='' if go_build_jobs is None else f'-p={go_build_jobs}',GOEXPERIMENT='',CGO_ENABLED='0')
            report['go_build_jobs']=go_build_jobs
            home=work/'home'; home.mkdir(); cache=work/'runtime-cache'; cache.mkdir()
            # pip downloads are build/test tooling, not mariamem runtime cache.
            env.update(HOME=str(home),XDG_CACHE_HOME=str(cache),PIP_CACHE_DIR=str(work/'pip-cache'))
            report['go_version']=subprocess.check_output(['go','version'],env=env,text=True).strip()
            project=work/'go-consumer'; project.mkdir()
            tag=metadata['GIT_TAG']
            if mode=='candidate':
                proxy=prepare_proxy(root,work,tag)
                env.update(GOPROXY=proxy.as_uri()+',https://proxy.golang.org',GONOSUMDB=MODULE)
            (project/'go.mod').write_text(f'module example.com/release-consumer\n\ngo 1.26.0\n\nrequire (\n {MODULE} {tag}\n github.com/go-sql-driver/mysql v1.9.3\n)\n')
            for source in (root/'tests/godefault').glob('*.go'):
                shutil.copyfile(source,project/source.name)
            if mode=='candidate': run(['go','mod','download',MODULE+'@'+tag],project,{**env,'GOPROXY':proxy.as_uri()})
            else:
                run(['go','mod','download',MODULE+'@'+tag],project,env)
                resolved=json.loads(subprocess.check_output(['go','list','-m','-json',MODULE],cwd=project,env=env,text=True))
                remote=json.loads(subprocess.check_output(['go','list','-m','-json',MODULE+'@'+tag],cwd=project,env={**env,'GOPROXY':'direct'},text=True))
                report['public_module']=bind_remote_origin(resolved,remote,commit,tag)
            run(['go','mod','tidy'],project,env)
            resolved=json.loads(subprocess.check_output(['go','list','-m','-json',MODULE],cwd=project,env=env,text=True))
            require(resolved['Version']==tag and 'Replace' not in resolved,'consumer module substituted')
            # These normal-path tests also reject cache/provisioning use, exercise
            # auth/errors/corruption/reconnect and retain closed handles explicitly.
            run(['go','test','-tags=integration','-count=1','-timeout=5m','-v','.'],project,env)
            report['steps'].update(go_default='PASS',go_snapshot_failure_lifecycle='PASS')
            gorm=work/'gorm'; shutil.copytree(root/'tests/consumer/gorm',gorm)
            run(['go','mod','edit','-require',MODULE+'@'+tag],gorm,env)
            run(['go','mod','tidy'],gorm,env)
            count=0
            for index,mode_name in enumerate(('start','fork','fork','start')):
                evidence=work/f'gorm-{index}.json'
                run(['go','test','-mod=readonly','-v','-count=1','-timeout=3m','.'],gorm,
                    {**env,'DOGFOOD_ZERO_OPTIONS':'1','DOGFOOD_MODE':mode_name,'DOGFOOD_EVIDENCE':str(evidence)})
                data=json.loads(evidence.read_text()); require(data['passed'] and len(data['cases'])==8,'GORM cases differ')
                count+=len(data['cases'])
            report['gorm_cases']=count; report['steps']['gorm']='PASS'
            venv=work/'venv'; run([sys.executable,'-m','venv',venv],work,env)
            python=venv/'bin/python'
            run([python,'-m','pip','install',str(selected)+'[test]','SQLAlchemy==2.0.54','pytest==8.4.2',
                 'pytest-xdist==3.8.0','PyMySQL==1.2.3'],work,env)
            run([python,root/'tests/verify_alpha.py'],work,env)
            shutil.copyfile(root/'tests/consumer/test_generated_platform.py',work/'test_generated_platform.py')
            run([python,'-m','pytest','-q',work/'test_generated_platform.py'],work,env)
            report['steps']['installed_wheel']='PASS'
            shutil.copyfile(root/'tests/consumer/test_sqlalchemy_dogfood.py',work/'test_sqlalchemy_dogfood.py')
            count=0
            for index,mode_name in enumerate(('start','fork','fork','start')):
                junit=work/f'sqlalchemy-{index}.xml'
                run([python,'-m','pytest','-q','test_sqlalchemy_dogfood.py','--junitxml',junit],work,
                    {**env,'DOGFOOD_MODE':mode_name,'DOGFOOD_EVIDENCE':str(work/f'sqlalchemy-{index}.json')})
                suites=list(ET.parse(junit).getroot().iter('testsuite'))
                require(sum(int(s.get('tests',0)) for s in suites)==11 and
                        all(int(s.get(k,0))==0 for s in suites for k in ('failures','errors','skipped')),'SQLAlchemy cases differ')
                count+=11
            report['sqlalchemy_cases']=count; report['steps']['sqlalchemy']='PASS'
            report['runtime_cache_entries']=sorted(p.name for p in cache.iterdir())
            require(not report['runtime_cache_entries'],'ordinary consumers unexpectedly used runtime cache: '+
                    ', '.join(report['runtime_cache_entries']))
        require(set(report['steps'])==STEPS,'missing acceptance stage')
        require(digest(selected)==report['wheel_sha256'],'wheel changed during acceptance')
        report['result']='PASS'
    except Exception as exc:
        report['error']=str(exc); raise
    finally: write(output,report)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=ROOT); p.add_argument('--candidate-sha',required=True)
    p.add_argument('--platform',required=True); p.add_argument('--output',type=Path,required=True)
    p.add_argument('--go-build-jobs',type=int,help='bound cold Go compilation without changing runtime concurrency')
    a=p.parse_args()
    if a.go_build_jobs is not None and a.go_build_jobs < 1: p.error('--go-build-jobs must be positive')
    print(json.dumps(accept(a.root,a.candidate_sha,a.platform,a.output,go_build_jobs=a.go_build_jobs),indent=2))

if __name__=='__main__': main()
