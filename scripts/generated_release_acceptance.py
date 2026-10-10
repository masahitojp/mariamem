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
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import urlopen
from common import ROOT, digest
from consumer_module import MODULE, prepare_proxy
from generated_release import CONTRACT, STEPS, checkout, require, source_inventory, verify_wheel, version, write
from consumer_acceptance import isolated_env, bind_remote_origin, environment, verify_module_files, ORM_MODES, verify_gorm_cases, verify_sqlalchemy_cases


def request_pkg_go_dev_discovery(root, tag):
    """Best-effort official proxy request; it is not pkg.go.dev qualification.

    https://pkg.go.dev/about#adding-a-package recommends a proxy endpoint request.
    A consumer's GOPROXY may fall back to direct; this request records the proxy
    result explicitly. Indexing is asynchronous: never wait/retry or gate smoke.
    """
    report={'module_version':tag, 'proxy_http_status':None,
            'proxy_fetch_result':'NOT_CONFIRMED', 'discovery_result':'NOT_CONFIRMED',
            'pkg_go_dev_listing':'NOT_CHECKED', 'required':False}
    try:
        match=re.search(r'^\s*module\s+(\S+)', (root/'go.mod').read_text(), re.MULTILINE)
        if not match: raise ValueError('go.mod module directive missing')
        module=match.group(1).strip('"`')
        # The Go proxy protocol escapes uppercase ASCII as !lowercase.
        escape=lambda value: ''.join('!'+c.lower() if 'A' <= c <= 'Z' else c for c in value)
        url='https://proxy.golang.org/'+quote(escape(module), safe='/!')+'/@v/'+quote(escape(tag), safe='!')+'.info'
        report.update(module_path=module, proxy_url=url,
                      documentation_url='https://pkg.go.dev/'+quote(module, safe='/')+'@'+quote(tag, safe=''))
        with urlopen(url, timeout=5) as response:
            report['proxy_http_status']=response.status
            info=json.loads(response.read(16384))
        if report['proxy_http_status'] != 200 or info.get('Version') != tag:
            raise ValueError('proxy response does not confirm the requested version')
        report.update(proxy_fetch_result='PASS', discovery_result='REQUESTED')
    except HTTPError as exc:
        report.update(proxy_http_status=exc.code, error=str(exc))
        exc.close()
    except Exception as exc:
        report['error']=str(exc)
    return report


def harness_inventory(root):
    paths=[root/'scripts/generated_release_acceptance.py', root/'scripts/consumer_module.py',
           root/'scripts/consumer_acceptance.py',root/'tests/verify_alpha.py',
           *sorted((root/'tests/godefault').glob('*.go')),
           root/'tests/consumer/test_database.py',root/'tests/consumer/test_generated_platform.py',
           root/'tests/consumer/test_sqlalchemy_dogfood.py', root/'scripts/guest_smoke/main.go',
           root/'tests/consumer/sqlalchemy-requirements.txt',
           *sorted((root/'tests/consumer/gorm').glob('*'))]
    return {p.relative_to(root).as_posix():digest(p) for p in paths if p.is_file()}


def accept(root, commit, platform, output, mode='candidate', wheel=None, go_build_jobs=None, publication=None,
           smoke_program=None, recovery=None):
    root=root.resolve(); output=output.resolve()
    require(not output.exists(),'refuse stale acceptance evidence')
    require(mode in ('candidate','published'),'unknown acceptance mode')
    require(smoke_program is None or (mode == 'published' and recovery is not None),
            'smoke override requires authenticated published recovery')
    if mode=='candidate': checkout(root,commit)
    selected,record=verify_wheel(root,platform,commit)
    if wheel is not None:
        require(wheel.resolve()==selected.resolve(),'selected wheel differs from frozen metadata')
    metadata=version(root)
    if mode=='published':
        require(publication is not None and publication.get('status')=='PUBLISHED'
                and publication.get('source_commit')==commit
                and publication.get('git_tag')==metadata['GIT_TAG']
                and publication['platforms'][platform]['result']=='READY'
                and publication['platforms'][platform]['wheel_record']==record,
                'published smoke requires exact accepted artifact proof')
    report={'contract':CONTRACT if mode=='candidate' else 'published-distribution-smoke-v1','result':'FAIL','source_commit':commit,'mode':mode,
             'platform':platform,'python_version':metadata['PYTHON_VERSION'],'module_version':metadata['GIT_TAG'],
             'wheel_sha256':record['sha256'],'go_source_sha256':source_inventory(root),
             'harness_sha256':harness_inventory(root),'steps':{},'runtime_overrides':False,
             'outside_checkout':True,'environment':environment(platform)}
    if smoke_program is not None:
        require(recovery.get('published_source_commit') == commit
                and recovery.get('smoke_program_sha256') == digest(smoke_program),
                'recovery program/source identity differs')
        report['recovery'] = recovery
        report['harness_sha256'].update(recovery.get('tooling_files_sha256', {}))
        report['harness_sha256']['scripts/guest_smoke/main.go'] = digest(smoke_program)
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
                report['public_module_fetch']={'goproxy':env['GOPROXY'], 'direct_fallback_allowed':True,
                                               'actual_transport':'NOT_OBSERVED'}
                run(['go','mod','download',MODULE+'@'+tag],project,env)
                resolved=json.loads(subprocess.check_output(['go','list','-m','-json',MODULE],cwd=project,env=env,text=True))
                remote=json.loads(subprocess.check_output(['go','list','-m','-json',MODULE+'@'+tag],cwd=project,env={**env,'GOPROXY':'direct'},text=True))
                report['public_module']=bind_remote_origin(resolved,remote,commit,tag)
                report['public_module_files']=verify_module_files(resolved,root)
            run(['go','mod','tidy'],project,env)
            resolved=json.loads(subprocess.check_output(['go','list','-m','-json',MODULE],cwd=project,env=env,text=True))
            require(resolved['Version']==tag and 'Replace' not in resolved,'consumer module substituted')
            if mode=='candidate':
                # These normal-path tests also reject cache/provisioning use, exercise
                # auth/errors/corruption/reconnect and retain closed handles explicitly.
                run(['go','test','-tags=integration','-count=1','-timeout=5m','-v','.'],project,env)
                report['steps'].update(go_default='PASS',go_snapshot_failure_lifecycle='PASS')
                # Exercise the exact public smoke program before publication too.
                # This includes the server-side COM_QUIT drain fixed in v0.4.5.
                smoke=work/'go-smoke'; smoke.mkdir()
                for name in ('go.mod','go.sum'):
                    shutil.copyfile(project/name,smoke/name)
                shutil.copyfile(root/'scripts/guest_smoke/main.go',smoke/'main.go')
                run(['go','run','.'],smoke,env)
                report['candidate_go_smoke']='PASS'
                gorm=work/'gorm'; shutil.copytree(root/'tests/consumer/gorm',gorm)
                run(['go','mod','edit','-require',MODULE+'@'+tag],gorm,env)
                run(['go','mod','tidy'],gorm,env)
                count=0
                for index,mode_name in enumerate(ORM_MODES):
                    evidence=work/f'gorm-{index}.json'
                    run(['go','test','-mod=readonly','-v','-count=1','-timeout=3m','.'],gorm,
                        {**env,'DOGFOOD_ZERO_OPTIONS':'1','DOGFOOD_MODE':mode_name,'DOGFOOD_EVIDENCE':str(evidence)})
                    count+=verify_gorm_cases(evidence)
                report['gorm_cases']=count; report['steps']['gorm']='PASS'
            else:
                for source in project.glob('*.go'): source.unlink()
                shutil.copyfile(smoke_program or root/'scripts/guest_smoke/main.go',project/'main.go')
                run(['go','run','.'],project,env)
                report['steps']['public_go_smoke']='PASS'
            venv=work/'venv'; run([sys.executable,'-m','venv',venv],work,env)
            python=venv/'bin/python'
            if mode=='candidate':
                run([python,'-m','pip','install',str(selected)+'[test]','-r',root/'tests/consumer/sqlalchemy-requirements.txt',
                     'pytest-xdist==3.8.0'],work,env)
                run([python,root/'tests/verify_alpha.py'],work,env)
                shutil.copyfile(root/'tests/consumer/test_generated_platform.py',work/'test_generated_platform.py')
                run([python,'-m','pytest','-q',work/'test_generated_platform.py'],work,env)
                report['steps']['installed_wheel']='PASS'
                shutil.copyfile(root/'tests/consumer/test_sqlalchemy_dogfood.py',work/'test_sqlalchemy_dogfood.py')
                count=0
                for index,mode_name in enumerate(ORM_MODES):
                    junit=work/f'sqlalchemy-{index}.xml'
                    run([python,'-m','pytest','-q','test_sqlalchemy_dogfood.py','--junitxml',junit],work,
                        {**env,'DOGFOOD_MODE':mode_name,'DOGFOOD_EVIDENCE':str(work/f'sqlalchemy-{index}.json')})
                    count+=verify_sqlalchemy_cases(junit)
                report['sqlalchemy_cases']=count; report['steps']['sqlalchemy']='PASS'
            else:
                run([python,'-m','pip','install',selected,'PyMySQL==1.2.3'],work,env)
                run([python,root/'tests/verify_alpha.py','--public-smoke'],work,env)
                installed=json.loads((root/'tests/evidence/public-wheel-smoke.json').read_text())
                require(installed['passed'] and installed['installed_files_match_wheel']
                        and installed['wheel_sha256']==record['sha256']
                        and installed['version']==metadata['PYTHON_VERSION'], 'public installed-wheel smoke differs')
                report['steps']['public_wheel_smoke']='PASS'
            report['runtime_cache_entries']=sorted(p.name for p in cache.iterdir())
            require(not report['runtime_cache_entries'],'ordinary consumers unexpectedly used runtime cache: '+
                    ', '.join(report['runtime_cache_entries']))
        required=STEPS if mode=='candidate' else {'public_go_smoke','public_wheel_smoke'}
        require(set(report['steps'])==required,'missing acceptance stage')
        require(digest(selected)==report['wheel_sha256'],'wheel changed during acceptance')
        if mode=='published':
            report['pkg_go_dev_discovery']=request_pkg_go_dev_discovery(root, publication['git_tag'])
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
