from support import *
import shutil,hashlib,platform
run('build-counter',['cc','-O2',R/'benchmarks/tools/process_cost.c','-o',helper])
run('build-python-host',['go','build','-p','1','-trimpath','-o',T/'mariamem-host','./cmd/mariamem-host'])
# Private experiment wheel through the real packaging recipe; no release approval.
pkg=T/'python';shutil.copytree(R/'python',pkg,ignore=shutil.ignore_patterns('_native','__pycache__','*.egg-info','build'))
native=pkg/'mariamem/_native';native.mkdir();shutil.copyfile(T/'mariamem-host',native/'mariamem-host');(native/'mariamem-host').chmod(0o755)
sys.path.insert(0,str(R/'scripts'));from native_target import current_target,platform_fields
version={};exec((pkg/'mariamem/_version.py').read_text(),version)
manifest={'version':1,'package_version':version['PYTHON_VERSION'],**platform_fields(current_target(R)),'runtime_kind':'generated-go','guest_sha256':json.loads((R/'release/generated-go-inputs.json').read_text())['guest_sha256'],'public_release_ready':False,'sha256':{'mariamem-host':hashlib.sha256((native/'mariamem-host').read_bytes()).hexdigest()}}
(native/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
for name in ['LICENSE','NOTICE','THIRD_PARTY_LICENSES']:shutil.copyfile(R/name,pkg/name)
shutil.copytree(R/'licenses',pkg/'licenses',dirs_exist_ok=True)
py=Path(os.environ.get('MARIAMEM_TEST_PYTHON',sys.executable))
venv=T/'venv';run('python-venv',[py,'-m','venv',venv]);py=venv/'bin/python'
run('python-dependencies',[py,'-m','pip','install','setuptools','wheel','pytest','PyMySQL','SQLAlchemy'],timeout=180)
run('build-wheel',[py,'-m','pip','wheel','--no-deps','--no-build-isolation','--wheel-dir',T/'wheels',pkg])
wheel=next((T/'wheels').glob('*.whl'));run('install-wheel',[py,'-m','pip','install','--no-deps',wheel])
record['wheel']={'sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),'host_sha256':manifest['sha256']['mariamem-host'],'installed':True};save()
run('installed-wheel-identity',[py,'-c','import mariamem;print(mariamem.__file__)'],cwd=T)
run('sqlalchemy',[py,R/'tests/consumer/run_sqlalchemy.py','--output',E/'sqlalchemy'],timeout=900)
project=T/'gorm';shutil.copytree(R/'tests/consumer/gorm',project,ignore=shutil.ignore_patterns('build'))
run('gorm-local-module',['go','mod','edit','-replace=github.com/masahitojp/mariamem='+str(R)],cwd=project)
for mode in ['start','fork']:
 run('gorm-'+mode,['go','test','-mod=mod','-p','1','-v','-count=1','-run=^TestDogfood$','.'],cwd=project,extras={'DOGFOOD_ZERO_OPTIONS':'1','DOGFOOD_MODE':mode,'DOGFOOD_EVIDENCE':str(E/('gorm-'+mode+'.json'))},timeout=300)
run('failure-reconnect',['go','test','-p','1','-tags=integration','-v','-count=1','-run=^TestDefaultReleaseFailurePaths$','-timeout=180s','./tests/godefault'],timeout=240)
record['products_pass']=True;save()
