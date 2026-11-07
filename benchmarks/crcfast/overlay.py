from pathlib import Path
import hashlib,json,runpy,sys,re,ast
s,o=map(lambda p:Path(p).resolve(),sys.argv[1:]);d=s/'benchmarks/crcfast'
# Inherited owner logs in ordinary runs; detailed timing only when requested.
runpy.run_path(str(s/'benchmarks/rsegvalidation/overlay.py'),run_name='__main__')
m=json.loads((o/'overlay.json').read_text());h=json.loads((o/'hashes.json').read_text())
p=s/'internal/generatedgo/code/p4/p4_pure.go';before=Path(m['Replace'][str(p)]).read_text();a=before.index('func Fn18145(');z=before.index('\nfunc ',a+1);f=before[a:z]
anchor='\nL23:\n\t;\n vc.CRCBegin(v40)';assert f.count(anchor)==1
f=f.replace(anchor,anchor+'\n if base.CRCFastEnabled { v495=int64(^base.CRCFast(m,l1,v40));goto L36 }')
after=before[:a]+f+before[z:];dest=o/'crc-fast-p4.go';dest.write_text(after);m['Replace'][str(p)]=str(dest);h.append(dict(path=str(p.relative_to(s)),before_sha256=hashlib.sha256(before.encode()).hexdigest(),after_sha256=hashlib.sha256(after.encode()).hexdigest()))
# Extract the exact original generated CRC region as a test reference.
raw=p.read_text();a=raw.index('func Fn18145(');z=raw.index('\nfunc ',a+1);f=raw[a:z];assert hashlib.sha256(f.encode()).hexdigest()=='e7f55f842faf017b47fa0d01d1bdb23a1fd19967644f617b6e4a6860662ebc09'
parts=re.split(r'\n(L\d+):\n',f);blocks={parts[i]:parts[i+1] for i in range(1,len(parts),2)};seen=set();pending=['L23']
while pending:
 n=pending.pop()
 if n in seen or n=='L36':continue
 seen.add(n);body=blocks[n];assert 'return ' not in body and 'Fn' not in body;edges=re.findall(r'goto (L\d+)',body);assert edges;pending+=edges
pre=f[f.index('\n\tmBase :='):f.index('\n\tv13 = m.G0')].replace('\n\tvar v40 int32\n\t_ = v40','')
ref='func crcOriginal(m *base.Module,l1,v40 int32)uint32{'+pre+'\n goto L23\n'+'\n'.join(n+':\n'+blocks[n] for n in sorted(seen,key=lambda x:int(x[1:])))+'\nL36:\nreturn ^uint32(v495)\n}\n'
g=(s/'internal/generatedgo/code/generated.go').read_text();literal=g.split('var wasm2goData_data_bin = []byte(',1)[1].split('\n',1)[0][:-1];data=ast.literal_eval(literal).encode('latin1');table=data[15555072-8388608:15555072-8388608+4096];assert len(table)==4096
unit=(d/'fast-test.go.txt').read_text().replace('// ORIGINAL_REFERENCE',ref).replace('TABLE_HEX',table.hex())
for target,body in [('internal/generatedgo/code/base/crc_fast.go',(d/'fast.go.txt').read_text()),('internal/generatedgo/code/p4/crc_fast_test.go',unit)]:
 out=o/Path(target).name;out.write_text(body);m['Replace'][str(s/target)]=str(out);h.append(dict(path=target,before_sha256=None,after_sha256=hashlib.sha256(body.encode()).hexdigest()))
(o/'overlay.json').write_text(json.dumps(m,indent=2)+'\n');(o/'hashes.json').write_text(json.dumps(h,indent=2)+'\n');(o/'crc-mapping.json').write_text(json.dumps(dict(source_function='Fn18145',replacement='L23 CRC compute only; original L36 complement, checksum comparison and LSN checks retained',crc_table_sha256=hashlib.sha256(table).hexdigest(),crc_reference_body_sha256=hashlib.sha256(ref.encode()).hexdigest(),original_body_sha256=hashlib.sha256(f.encode()).hexdigest(),ordinary='same instrumented binary with detailed timing disabled; owner logging enabled in both arms'),indent=2)+'\n')
