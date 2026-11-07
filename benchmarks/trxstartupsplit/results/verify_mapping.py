from pathlib import Path
import json,hashlib,re,sys
s=Path(sys.argv[1]).resolve();b=s/'benchmarks/trxstartupsplit';v=json.loads((b/'layout.json').read_text());p=s/'internal/generatedgo/code/p2/p2_pure.go';t=p.read_text();assert hashlib.sha256(t.encode()).hexdigest()==v['p2_sha256'];a=t.index('func Fn18291(');z=t.index('\nfunc ',a+1);f=t[a:z];assert hashlib.sha256(f.encode()).hexdigest()==v['body_sha256']
for q in v['checks']:assert f.count(q)==1,q
m=re.search(r'^func Fn17233\(',t,re.M);assert m;z=t.index('\nfunc ',m.end());f=t[m.start():z];assert 'int32(8428772)' in f and 'int32(17897664)' in f
print('PASS pinned transaction caller, inline purge entry, rseg call and undo-branch mapping')
