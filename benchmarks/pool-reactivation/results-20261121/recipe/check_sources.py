"""Verify two independent transformations and the constructor-image contract."""
import hashlib,json,subprocess,sys
from pathlib import Path
w=Path(sys.argv[1]).resolve()
src=w/'worktree'
base='a1ce4a7d568fbf6eac7bee032a7fdfbe464544fb'
runtime=src/'internal/generatedgo'
paths=['code/p3/p3_pure.go','code/p5/p5_pure.go']
def old(name):
    return subprocess.check_output(['git','show',base+':internal/generatedgo/'+name],cwd=src)
def sha(b):return hashlib.sha256(b).hexdigest()
layout=json.loads((runtime/'image/layout.json').read_bytes())
baseline=json.loads(old('image/layout.json'))
assert layout.keys()==baseline.keys()
assert all(layout[k]==v for k,v in baseline.items() if k!='source_sha256')
changed=[k for k,v in baseline['source_sha256'].items() if layout['source_sha256'][k]!=v]
assert set(changed)=={'internal/generatedgo/'+p for p in paths}
files={}
for name in paths:
    built=(runtime/name).read_bytes()
    assert all((w/'temp'/replay/name).read_bytes()==built for replay in ('replay-a','replay-b'))
    files[name]={'original':sha(old(name)),'candidate':sha(built)}
    assert layout['source_sha256']['internal/generatedgo/'+name]==files[name]['candidate']
record=json.loads((runtime/'provenance.json').read_bytes())
base_record=json.loads(old('provenance.json'))
assert {k for k,v in base_record['files_sha256'].items() if record['files_sha256'][k]!=v}==set(paths+['image/layout.json'])
assert record['guest_sha256']==base_record['guest_sha256']
subprocess.run([sys.executable,'-B',src/'scripts/verify_generated_runtime.py'],cwd=src,check=True)
print(json.dumps(dict(guest=record['guest_sha256'],outputs=files,layout=sha((runtime/'image/layout.json').read_bytes()),memory=layout['memory_sha256']),indent=2))
