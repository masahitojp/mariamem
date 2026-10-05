from support import *
import shutil,re,hashlib
run('build-counter',['cc','-O2',R/'benchmarks/tools/process_cost.c','-o',helper])
host=Path(os.environ['MARIAMEM_PRODUCT_TEMP'])/'mariamem-host'
run('candidate-symbols',['go','tool','nm',host]);symbols=(E/'candidate-symbols.log').read_text()
p=R/'release/generated-license-evidence.json';e=json.loads(p.read_text());checked=[]
for component,row in e['retained_symbols'].items():
 for example in row['examples']:
  path=R/example['generated_file'];name=example['generated_function'];assert 'func '+name+'(' in path.read_text()
  assert re.search(r'/code/'+re.escape(path.parent.name)+r'\.'+re.escape(name)+r'(?:\.abi0)?$',symbols,re.M),name
  checked.append({'component':component,**example,'candidate_symbol_retained':True})
e['generated_provenance_sha256']=hashlib.sha256((R/'internal/generatedgo/provenance.json').read_bytes()).hexdigest()
e['mmap_integration_candidate_check']={'released_base':'547fb1a6c01e5edb0daa27de273a2e94e66eb098','semantics_basis':'56be628bf2d976048c5ea6d1949879781ed75342','mmap_basis':'b9975c3ae33848442704007ad2647bd76e52a602','host_sha256':hashlib.sha256(host.read_bytes()).hexdigest(),'generated_provenance_sha256':e['generated_provenance_sha256'],'examples':checked,'note':'Private integration experiment, same guest/function map; native retention checked. Not release approval.'}
p.write_text(json.dumps(e,indent=2)+'\n');p=R/'release/distribution-licenses.json';inv=json.loads(p.read_text());inv['evidence_sha256']=hashlib.sha256((R/'release/generated-license-evidence.json').read_bytes()).hexdigest();p.write_text(json.dumps(inv,indent=2)+'\n');shutil.copyfile(p,R/'python/license-inventory.json')
record['retained_license_examples']=len(checked);save()
run('provenance',[sys.executable,R/'scripts/verify_generated_runtime.py'])
py=os.environ.get('MARIAMEM_CHECK_PYTHON',sys.executable)
run('canonical-check',[py,R/'scripts/verify.py','check'],timeout=900)
cache=Path(os.environ['MARIAMEM_CACHE']);guest=Path(os.environ['MARIAMEM_RELEASE_GUEST']);tools=json.loads((R/'release/generated-go-toolchain.json').read_text());download=R/'build/downloads'/tools['archives']['converter']['file'];download.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(cache/'wasm2go-fork.tar.gz',download)
g=T/'guest';g.mkdir();shutil.copyfile(guest,g/'mariamem.wasm');shutil.copyfile(guest.parent/'guest.json',g/'guest.json')
run('independent-regeneration',[sys.executable,R/'scripts/regenerate_release_guest.py','--guest-dir',g,'--output',T/'regeneration'],timeout=900)
record['proof_pass']=True;save()
