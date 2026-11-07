"""Static mapping proof. Run from the experiment worktree before build/run."""
from pathlib import Path
import re,json,hashlib
s=Path.cwd();layout=json.loads((s/'benchmarks/innodbopenspan/layout.json').read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
p0=s/'internal/generatedgo/code/p0/p0_pure.go';p2=s/'internal/generatedgo/code/p2/p2_pure.go'
assert sha(p0)==layout['p0_sha256'] and sha(p2)==layout['p2_sha256']
text=(s/'internal/generatedgo/code/generated.go').read_text();needle='var wasm2goData_data_bin = []byte("';a=text.index(needle)+len(needle);b=text.index('")',a);raw=text[a:b];assert re.fullmatch(r'(?:\\x[0-9a-fA-F]{2})+',raw)
data=bytes.fromhex(raw.replace('\\x',''));inputs=json.loads((s/'release/generated-go-inputs.json').read_text());assert hashlib.sha256(data).hexdigest()==inputs['data_sha256']
def function(p,name):
 text=p.read_text();m=re.search(r'^func '+name+r'\(',text,re.M);assert m;end=text.find('\nfunc ',m.end());assert end>0;return text[m.start():end]
caller=function(p0,'Fn18569');callee=function(p2,'Fn16690')
for key in ['marker_begin','marker_end']:
 q=layout[key];offset=data.index(q['text'].encode());assert offset+8388608==q['address'];assert caller.count('Fn227(m, int32('+str(q['address'])+'))')==1
call='v11116 = Fn16690(m, int32(26778912), int32(0), v11097, v11085+int32(792))';assert caller.count(call)==1
assert caller.index('Fn227(m, int32(8620240))')<caller.index(call)<caller.index('Fn227(m, int32(8619848))')
proof_strings=['InnoDB: Failed to read the first double write buffer extent','InnoDB: Failed to read the second double write buffer extent','InnoDB: Failed to read the system tablespace header page','InnoDB: The data file \'%s\' has the wrong space ID. It should be %u, but %u was found','/work/source/storage/innobase/fsp/fsp0sysspace.cc']
for term in proof_strings:
 offset=data.index(term.encode());assert 'int32('+str(8388608+offset)+')' in callee
assert 'func Fn16690(m *base.Module, l0 int32, l1 int32, l2 int32, l3 int32) int32' in callee
assert 'if l3 == int32(0)' in callee and 'if l2 != 0' in callee
aliases=(s/'internal/generatedgo/code/p0/alias.go').read_text();assert '//go:linkname Fn16690 github.com/masahitojp/mariamem/internal/generatedgo/code/p2.Fn16690' in aliases
out={'result':'PASS','data_sha256':inputs['data_sha256'],'caller':'Fn18569','callee':'Fn16690','caller_body_sha256':hashlib.sha256(caller.encode()).hexdigest(),'callee_body_sha256':hashlib.sha256(callee.encode()).hexdigest(),'proof_strings':proof_strings,'layout_sha256':sha(s/'benchmarks/innodbopenspan/layout.json'),'guest_sha256':inputs['guest_sha256']}
(s.parent/'evidence/mapping-verification.json').write_text(json.dumps(out,indent=2)+'\n');print('PASS: marker/data/call/alias/signature/callee strings match pinned layout')
