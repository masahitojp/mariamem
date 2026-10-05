import sys,os,subprocess,tarfile,difflib,json,hashlib,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[3];T=Path(os.environ['MARIAMEM_EXPERIMENT_TEMP']);E=Path(os.environ['MARIAMEM_EXPERIMENT_EVIDENCE'])
cache=Path(os.environ['MARIAMEM_CACHE']);guest=Path(os.environ['MARIAMEM_RELEASE_GUEST'])
assert hashlib.sha256((cache/'wasm2go-fork.tar.gz').read_bytes()).hexdigest()=='1fcd91eecc66e367495d91f34644c68df1ff856a786d00c24fa66061c3dbce0f'
x=T/'patch-source';x.mkdir()
with tarfile.open(cache/'wasm2go-fork.tar.gz') as tar:tar.extractall(x,filter='data')
s=next(x.iterdir());patches=R/'benchmarks/spikes/wasm2go'
for p in ['imported-memory.patch','import-function-index.patch','relaxed-madd.patch','pure-memory32.patch']:
 subprocess.run(['git','apply','--unidiff-zero',str(patches/p)],cwd=s,check=True)
changes={}
f='internal/codegen/translate.go';before=(s/f).read_text();needle='\t\tthreadStartField, argType := "threadStart", "int32"'
addition='\t\t// Optional shared memory32 owner: prepare pages before publishing size.\n\t\tfields = append(fields, &ast.Field{\n\t\t\tNames: []*ast.Ident{newID(t.fieldName("prepareMemoryGrow"))},\n\t\t\tType: &ast.FuncType{Params: &ast.FieldList{List: []*ast.Field{\n\t\t\t\t{Type: newID("uint64")}, {Type: newID("uint64")},\n\t\t\t}}, Results: &ast.FieldList{List: []*ast.Field{{Type: newID("error")}}}},\n\t\t})\n'
assert needle in before;changes[f]=(before,before.replace(needle,addition+needle))
f='internal/codegen/helpers/helpers.go';before=(s/f).read_text();after=before.replace('memShared bool','memShared bool\n prepareMemoryGrow func(uint64,uint64) error',1)
needle='\t\tm.memSize.Store(want)\n\t\treturn prev'
assert needle in after;after=after.replace(needle,'\t\tif m.prepareMemoryGrow != nil {\n\t\t\tif err := m.prepareMemoryGrow(cur,want); err != nil { return -1 }\n\t\t}\n'+needle,1);changes[f]=(before,after)
patch=''
for f,(before,after) in changes.items():
 (s/f).write_text(after);patch+=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/'+f,tofile='b/'+f))
(patches/'linear-memory-owner.patch').write_text(patch)
env=dict(os.environ,GOTOOLCHAIN='go1.26.8',GOWORK='off')
def run(name,args):
 print(name,flush=True)
 with (E/(name+'.log')).open('w') as log:subprocess.run(list(map(str,args)),cwd=R,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
run('translate',[sys.executable,R/'benchmarks/spikes/generated-go-integration/translate_guest.py','--guest',guest,'--guest-sha256',hashlib.sha256(guest.read_bytes()).hexdigest(),'--converter-archive',cache/'wasm2go-fork.tar.gz','--output',T/'translation'])
shutil.copyfile(T/'translation/input-manifest.json',R/'release/generated-go-translation.json')
run('prepare-candidate',[sys.executable,R/'benchmarks/spikes/generated-go-integration/setup_candidate.py','--source-only','--source-module',T/'translation/module','--guest',guest,'--input-manifest',R/'release/generated-go-translation.json','--output',T/'candidate'])
p=R/'release/generated-go-inputs.json';pins=json.loads(p.read_text());module=T/'candidate/module';pins['candidate_files_sha256']={str(f.relative_to(module)):hashlib.sha256(f.read_bytes()).hexdigest() for suffix in ('*.go','*.s') for f in module.rglob(suffix)};p.write_text(json.dumps(pins,indent=2)+'\n')
run('generate-runtime',[sys.executable,R/'scripts/generate_runtime.py','--source-module',module,'--output',T/'generatedgo'])
for f in (T/'generatedgo').rglob('*'):
 if f.is_file():
  target=R/'internal/generatedgo'/f.relative_to(T/'generatedgo');target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,target)
run('fixture-heap',[sys.executable,R/'benchmarks/spikes/memory-candidate/check_fixture.py','--converter',T/'translation/wasm2go','--output',T/'fixture-heap'])
run('provenance',[sys.executable,R/'scripts/verify_generated_runtime.py'])
print('PREPARE PASS',flush=True)
