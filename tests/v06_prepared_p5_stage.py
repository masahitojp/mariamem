"""Private P5 wheel from the already bound UNQUALIFIED development host.

Never changes canonical inventories, invokes release packaging or publishes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from native_target import current_target, platform_fields
from dev_guest import CONTRACT, external_output, require, source_identity


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_inputs(development, expected_commit, expected_guest):
    development=Path(development)
    r=json.loads((development/'development.json').read_text())
    require(r['contract']==CONTRACT and r['result']=='UNQUALIFIED' and r['smoke']=='PASS','not a passed unqualified development host')
    require(r['source_identity']['commit']==expected_commit and r['host_source_identity']['commit']==expected_commit,'development host candidate commit mismatch')
    require(r['guest_sha256']==expected_guest,'unexpected prepared development guest')
    require(digest(development/'mariamem-dev-host')==r['binary_sha256'],'mixed development host binary')
    # SDK bytes consumed by wheel staging must be the tested installed-source SDK.
    files=r['host_source_identity']['files_sha256']
    actual={}
    for path in (development/'product/python').rglob('*'):
        require(not path.is_symlink(),'symlink in staged SDK')
        if path.is_file() and '__pycache__' not in path.parts and not path.name.endswith('.pyc'):
            key=path.relative_to(development/'product').as_posix()
            actual[key]=digest(path)
    expected={k:v for k,v in files.items() if k.startswith('python/')}
    require(actual==expected,'unbound/missing SDK inputs')
    return r


def main():
    p=argparse.ArgumentParser();p.add_argument('--development',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    identity=source_identity(ROOT)
    expected=json.loads((ROOT/'tests/fixtures/prepared-p2-binding/identity.json').read_text())['guest_sha256']
    r=verify_inputs(a.development,identity['commit'],expected)
    work=external_output(ROOT,a.work.resolve());work.mkdir(parents=True)
    package=work/'python'
    shutil.copytree(a.development/'product/python',package,ignore=shutil.ignore_patterns('_native','build','*.egg-info','__pycache__'))
    for name in ('LICENSE','NOTICE','THIRD_PARTY_LICENSES'):shutil.copyfile(ROOT/name,package/name)
    shutil.copytree(ROOT/'licenses',package/'licenses',dirs_exist_ok=True)
    native=package/'mariamem/_native';native.mkdir()
    host=native/'mariamem-host';shutil.copy2(a.development/'mariamem-dev-host',host);host.chmod(0o755)
    version=runpy.run_path(str(package/'mariamem/_version.py'))['PYTHON_VERSION']
    target=current_target(ROOT)
    manifest={'version':1,'package_version':version,**platform_fields(target),'runtime_kind':'generated-go','guest_sha256':r['guest_sha256'],'public_release_ready':False,'development_contract':CONTRACT,'source_commit':identity['commit'],'sha256':{'mariamem-host':digest(host)}}
    (native/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    result={'scope':'private P5 development wheel only; NOT Release eligible','source_commit':identity['commit'],'guest_sha256':r['guest_sha256'],'host_sha256':digest(host),'development_receipt_sha256':digest(a.development/'development.json'),'manifest':manifest,'result':'FAIL'}
    try:
        run=subprocess.run([sys.executable,'-m','pip','wheel','--no-deps','--no-build-isolation','--no-cache-dir','--wheel-dir',str(work/'dist'),str(package)],capture_output=True,text=True,timeout=180)
        (work/'wheel.txt').write_text(run.stdout+run.stderr);require(run.returncode==0,'private wheel build failed: '+str(work/'wheel.txt'))
        wheels=list((work/'dist').glob('*.whl'));require(len(wheels)==1,'ambiguous private wheel')
        wheel=wheels[0];result.update(wheel=str(wheel),wheel_sha256=digest(wheel))
        subprocess.run([sys.executable,'-m','pip','install','--force-reinstall','--no-deps',str(wheel)],check=True,timeout=120)
        result['result']='PASS'
    except Exception as e:result['error']=repr(e);raise
    finally:
        a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
