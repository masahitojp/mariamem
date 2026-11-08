"""Acquire exact new-guest translations; deliberately stop before fixed runtime bindings."""
from pathlib import Path
import argparse,json,subprocess,sys,os,hashlib,platform,shutil
S=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(S/'scripts'))
from dev_guest import verify_guest,source_identity
from build_generated_guest import download
from common import digest

def main():
 p=argparse.ArgumentParser();p.add_argument('--guest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);a.receipt.mkdir(parents=True,exist_ok=True)
 identity=source_identity(S);assert identity['commit']==os.environ['GITHUB_SHA']
 guest=verify_guest(S,a.guest);assert guest['source_commit']==identity['commit'] and guest['result']=='UNQUALIFIED'
 tools=json.loads((S/'release/generated-go-toolchain.json').read_text());converter=download(tools['archives']['converter'],a.output/'downloads')
 translation=a.output/'translation'
 subprocess.run([sys.executable,str(S/'benchmarks/spikes/generated-go-integration/translate_guest.py'),'--guest',str((a.guest/'mariamem.wasm').resolve()),'--guest-sha256',guest['guest_sha256'],'--converter-archive',str(converter.resolve()),'--output',str(translation.resolve())],cwd=S,check=True)
 raw=json.loads((translation/'input-manifest.json').read_text());assert raw['guest_sha256']==guest['guest_sha256']
 assert source_identity(S)==identity
 # These guards intentionally still pin the adopted old guest. Never weaken or
 # silently disable them to get a new guest through the installer.
 guard_files=['scripts/runtime_thread_lifetime.py','scripts/runtime_crc32c.py','scripts/runtime_failure.py','scripts/runtime_write.py','scripts/runtime_atomic_loads.py','scripts/runtime_memfs.py']
 result={'result':'PASS_INPUT_AND_TRANSLATION_ONLY','source_commit':identity['commit'],'guest_sha256':guest['guest_sha256'],'platform':platform.platform(),'machine':platform.machine(),'converter_commit':raw['converter_commit'],'generated_files_sha256':raw['files_sha256'],'runtime_binding_guards_sha256':{n:digest(S/n) for n in guard_files},'next_gate':'Inspect new translated identities and rebind exact reviewed host transformations before installation; existing old-guest bindings are not reused or bypassed.','actual_guest_acceptance':'NOT_RUN','native_sql_differential':'NOT_RUN','performance':'NOT_MEASURED_FOR_C_GUEST','independent_c_builds':1,'qualification':'NOT_RUN','adoption':'NOT_APPROVED'}
 (a.receipt/'result.json').write_text(json.dumps(result,indent=2)+'\n');shutil.copy2(translation/'input-manifest.json',a.receipt/'input-manifest.json');print(result['result'])
if __name__=='__main__':main()
