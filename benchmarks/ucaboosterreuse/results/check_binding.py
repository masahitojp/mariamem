from pathlib import Path
import sys,os,json,tempfile,shutil
w=Path(__file__).resolve().parents[1];s=w/'temp/source';e=w/'evidence';src=w/'temp/abi-preflight/candidate/module';sys.path.insert(0,str(s/'scripts'));import generate_runtime as g,runtime_thread_lifetime as b
m=json.loads((e/'experimental-binding.json').read_text());pins={'guest_sha256':m['guest_sha256']};files=m['candidate_files_sha256'];os.environ['MARIAMEM_EXPERIMENT_THREAD_BINDING']=str(e/'experimental-binding.json');passed=[]
def reject(name,f):
 try:f()
 except ValueError:passed.append(name);return
 raise AssertionError(name)
a=g.experimental_thread_binding(src,pins,files,True);assert a and b.FUNCTIONS=={k:tuple(v) for k,v in m['canonical_functions'].items()};passed.append('fixed candidate accepted without canonical state mutation')
reject('release override rejected',lambda:g.experimental_thread_binding(src,pins,files,False));reject('unknown guest rejected',lambda:g.experimental_thread_binding(src,{'guest_sha256':'0'*64},files,True));reject('inventory mutation rejected',lambda:g.experimental_thread_binding(src,pins,{},True))
with tempfile.TemporaryDirectory(dir=w/'temp') as d:
 t=Path(d);shutil.copytree(src/'generated',t/'generated');p=t/'generated/data.bin';orig=p.read_bytes();p.write_bytes(b'x'+orig[1:]);reject('data mutation rejected',lambda:g.experimental_thread_binding(t,pins,files,True));p.write_bytes(orig)
 p=t/'generated/p3/p3_pure.go';text=p.read_text();p.write_text(text.replace('func Fn153(m *base.Module, l0 int32) {','func Fn153(m *base.Module, l0 int32) {\n panic("mutation")',1));reject('closure mutation rejected',lambda:g.experimental_thread_binding(t,pins,files,True))
 p=t/'manifest.json';p.write_text((e/'experimental-binding.json').read_text()+' ');os.environ['MARIAMEM_EXPERIMENT_THREAD_BINDING']=str(p);reject('manifest mutation rejected',lambda:g.experimental_thread_binding(src,pins,files,True));os.environ['MARIAMEM_EXPERIMENT_THREAD_BINDING']=str(e/'experimental-binding.json')
original=b.FUNCTIONS;text=(src/'generated/p3/p3_pure.go').read_text();adapted=g.apply_thread_binding('code/p3/p3_pure.go',text,a);assert adapted.count('if base.DeferThreadAllocationFree(m, l0) { return }')==1 and b.FUNCTIONS is original;passed.append('exact handoff installed; original binding restored')
reject('bad adapter body rejected',lambda:g.apply_thread_binding('code/p3/p3_pure.go',text.replace('func Fn153(m *base.Module, l0 int32) {','func Fn153(m *base.Module, l0 int32) {\n panic("mutation")',1),a));assert b.FUNCTIONS is original;passed.append('exception restores original binding')
os.environ.pop('MARIAMEM_EXPERIMENT_THREAD_BINDING');assert g.experimental_thread_binding(src,pins,files,True) is None;reject('unreviewed guest still rejected by canonical guard',lambda:b.validate_inputs(pins['guest_sha256'],files));b.validate_inputs(b.GUEST_SHA256,files)
(e/'binding-check.json').write_text(json.dumps({'result':'PASS','checks':passed},indent=2)+'\n');print(passed)
