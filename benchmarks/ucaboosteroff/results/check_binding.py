import os,sys,json,tempfile,shutil,hashlib
from pathlib import Path
w=Path(__file__).resolve().parents[1];s=w/'temp/source';e=w/'evidence';src=w/'temp/dev-native/candidate/module'
sys.path.insert(0,str(s/'scripts'));import generate_runtime as g, runtime_thread_lifetime as b
m=json.loads((e/'experimental-binding.json').read_text());pins={'guest_sha256':m['guest_sha256']};files=m['candidate_files_sha256'];os.environ['MARIAMEM_EXPERIMENT_THREAD_BINDING']=str(e/'experimental-binding.json')
assert g.experimental_thread_binding(src,pins,files,True)==b.GUEST_SHA256
passed=['exact guest accepted']
def rejects(label,call):
 try:call()
 except ValueError:passed.append(label);return
 raise AssertionError(label)
rejects('release rejects override',lambda:g.experimental_thread_binding(src,pins,files,False))
rejects('unknown guest rejected',lambda:g.experimental_thread_binding(src,{'guest_sha256':'0'*64},files,True))
rejects('inventory mutation rejected',lambda:g.experimental_thread_binding(src,pins,{},True))
with tempfile.TemporaryDirectory(dir=w/'temp') as d:
 t=Path(d);shutil.copytree(src/'generated',t/'generated')
 p=t/'generated/data.bin';original=p.read_bytes();p.write_bytes(b'x'+original[1:]);rejects('data mutation rejected',lambda:g.experimental_thread_binding(t,pins,files,True));p.write_bytes(original)
 p=t/'generated/p3/p3_pure.go';p.write_text(p.read_text().replace('func Fn153(m *base.Module, l0 int32) {','func Fn153(m *base.Module, l0 int32) {\n panic("mutation")',1));rejects('body mutation rejected',lambda:g.experimental_thread_binding(t,pins,files,True))
os.environ.pop('MARIAMEM_EXPERIMENT_THREAD_BINDING');rejects('canonical guard rejects unknown guest',lambda:b.validate_inputs(g.experimental_thread_binding(src,pins,files,True),files));b.validate_inputs(b.GUEST_SHA256,files);passed.append('canonical guest unchanged')
(e/'binding-check.json').write_text(json.dumps({'result':'PASS','checks':passed},indent=2)+'\n');print(passed)
