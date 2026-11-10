"""Reproduce the exact adopted guest to obtain its current symbol map."""
from pathlib import Path
import hashlib,json,os,subprocess,tarfile,zipfile,sys
S=Path(__file__).resolve().parents[2];T=S.parent/'temp';E=S.parent/'evidence'
sys.path.insert(0,str(S/'scripts'))
from git_identity import require_commit
p=json.loads((Path(__file__).parent/'plan.json').read_text());require_commit(S,p['source_commit'])
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(a,**kw):subprocess.run(a,check=True,timeout=240,**kw)
z=T/'guest.zip'
with z.open('wb') as f:run(['gh','api','repos/masahitojp/mariamem/actions/artifacts/13628982950/zip'],stdout=f)
g=T/'guest';g.mkdir()
with zipfile.ZipFile(z) as a:
 for n in a.namelist():assert not Path(n).is_absolute() and '..' not in Path(n).parts
 a.extractall(g)
print('artifact files',[(x.name,x.stat().st_size) for x in g.rglob('*') if x.is_file()],flush=True)
b=T/'binaryen.tar.gz';run(['curl','-fLsS','https://github.com/WebAssembly/binaryen/releases/download/version_133/binaryen-version_133-arm64-macos.tar.gz','-o',str(b)])
assert sha(b)=='ad66da82ac13f163e424b1643f16c6dfcccc98b5966296b43e52d3cab04f84a8'
d=T/'binaryen';d.mkdir()
with tarfile.open(b) as a:
 for n in a.getnames():assert not Path(n).is_absolute() and '..' not in Path(n).parts
 a.extractall(d)
linked=next(g.rglob('linked.wasm'));guest=next(g.rglob('mariamem.wasm'))
assert sha(guest)==json.loads((S/'internal/generatedgo/provenance.json').read_text())['guest_sha256']
cmd=[str(d/'binaryen-version_133/bin/wasm-opt'),'-O2','--enable-threads','--enable-mutable-globals','--enable-bulk-memory','--enable-bulk-memory-opt','--enable-exception-handling','--enable-simd','--enable-relaxed-simd','--enable-extended-const',str(linked),'-o',str(T/'mapped.wasm'),'--print-function-map']
with (T/'function-map.txt').open('w') as f:run(cmd,stdout=f,env=dict(os.environ,BINARYEN_CORES='1'))
assert sha(T/'mapped.wasm')==sha(guest)
assert sha(T/'function-map.txt')==p['symbol_map_sha256']
(E/'function-map-proof.json').write_text(json.dumps(dict(guest_sha256=sha(guest),linked_sha256=sha(linked),symbol_map_sha256=sha(T/'function-map.txt'),artifact_id=13628982950,artifact_archive_sha256=sha(z),binaryen_archive_sha256=sha(b),result='EXACT_GUEST_AND_MAP'),indent=2)+'\n')
print('EXACT GUEST AND MAP',flush=True)
