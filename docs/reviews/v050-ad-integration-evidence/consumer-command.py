"""Bounded existing consumers against private exact-source module/wheel only."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

root=Path.cwd().resolve(); task=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(root/'scripts'))
from consumer_module import MODULE, prepare_proxy, source_identity
from consumer_acceptance import isolated_env, verify_module_files, verify_installed_files, ORM_MODES, verify_gorm_cases, verify_sqlalchemy_cases
from generated_release import checkout, verify_wheel
from common import digest

commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
checkout(root,commit)
wheel, wheel_record=verify_wheel(root,'darwin-arm64',commit)
work=task/'temp/consumers'; work.mkdir()
env=isolated_env(work)
env={k:v for k,v in env.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_','PYTHON','PYTEST','DOGFOOD_'))}
env.update(GOTOOLCHAIN='go1.26.8',GOMAXPROCS='2',GOFLAGS='-p=1',
    GOPATH=str(task/'temp/gopath'),GOMODCACHE=str(task/'temp/modcache'),GOCACHE=str(task/'temp/gocache'))
proxy=prepare_proxy(root,work,'v0.4.7')
env.update(GOPROXY=proxy.as_uri()+',https://proxy.golang.org',GONOSUMDB=MODULE)
log=task/'evidence/consumers.log'
report={'source_commit':commit,'go_source_identity':source_identity(root),'wheel_sha256':digest(wheel),
    'result':'FAIL','private_only':True,'module_version':'v0.4.7','steps':{},'GOTOOLCHAIN':'go1.26.8'}
def run(command,cwd=work, extra=None):
    with log.open('a') as stream:
        stream.write(json.dumps(list(map(str,command)))+'\n');stream.flush()
        subprocess.run(list(map(str,command)),cwd=cwd,env={**env,**(extra or {})},stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=1200)
try:
    project=work/'go';project.mkdir()
    (project/'go.mod').write_text(f'module example.com/ad-consumer\n\ngo 1.26.0\nrequire (\n {MODULE} v0.4.7\n github.com/go-sql-driver/mysql v1.9.3\n)\n')
    for file in (root/'tests/godefault').glob('*.go'): shutil.copy2(file,project/file.name)
    run(['go','mod','tidy'],project)
    resolved=json.loads(subprocess.check_output(['go','list','-m','-json',MODULE],cwd=project,env=env,text=True))
    assert resolved['Version']=='v0.4.7' and 'Replace' not in resolved
    report['module_files']=verify_module_files(resolved,root)
    run(['go','test','-tags=integration','-count=1','-timeout=5m','-v','.'],project)
    smoke=work/'go-smoke';smoke.mkdir()
    for name in ('go.mod','go.sum'): shutil.copy2(project/name,smoke/name)
    shutil.copy2(root/'scripts/guest_smoke/main.go',smoke/'main.go')
    run(['go','run','.'],smoke)
    report['steps']['go_consumer']='PASS'
    gorm=work/'gorm';shutil.copytree(root/'tests/consumer/gorm',gorm)
    run(['go','mod','edit','-require',MODULE+'@v0.4.7'],gorm)
    run(['go','mod','tidy'],gorm)
    count=0
    for index,mode in enumerate(ORM_MODES):
        evidence=task/'evidence'/f'gorm-{index}.json'
        run(['go','test','-mod=readonly','-v','-count=1','-timeout=3m','.'],gorm,
            {'DOGFOOD_ZERO_OPTIONS':'1','DOGFOOD_MODE':mode,'DOGFOOD_EVIDENCE':str(evidence)})
        count+=verify_gorm_cases(evidence)
    report['gorm_cases']=count;assert count==32
    report['steps']['gorm']='PASS'
    venv=work/'venv';run([sys.executable,'-m','venv',venv])
    python=venv/'bin/python'
    run([python,'-m','pip','install',wheel,'pytest','pymysql==1.2.3','sqlalchemy==2.0.54'])
    installed=Path(subprocess.check_output([python,'-c','import pathlib,mariamem;print(pathlib.Path(mariamem.__file__).parent)'],cwd=work,env=env,text=True).strip())
    verify_installed_files(wheel,installed)
    assert not installed.is_relative_to(root)
    shutil.copy2(root/'tests/consumer/test_generated_platform.py',work/'test_generated_platform.py')
    run([python,'-m','pytest','-q','test_generated_platform.py'])
    report['steps']['python_consumer']='PASS'
    shutil.copy2(root/'tests/consumer/test_sqlalchemy_dogfood.py',work/'test_sqlalchemy_dogfood.py')
    count=0
    for index,mode in enumerate(ORM_MODES):
        junit=task/'evidence'/f'sqlalchemy-{index}.xml'
        run([python,'-m','pytest','-q','test_sqlalchemy_dogfood.py','--junitxml',junit],work,
            {'DOGFOOD_MODE':mode,'DOGFOOD_EVIDENCE':str(task/'evidence'/f'sqlalchemy-{index}.json')})
        count+=verify_sqlalchemy_cases(junit)
    report['sqlalchemy_cases']=count;assert count==44
    report['steps']['sqlalchemy']='PASS'
    report['result']='PASS'
finally:
    (task/'evidence/consumer-results.json').write_text(json.dumps(report,indent=2)+'\n')
