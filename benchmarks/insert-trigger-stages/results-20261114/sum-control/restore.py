"""Run after copying this result bundle into a prepared workspace's evidence/."""
from pathlib import Path
import json,shutil,subprocess,hashlib
W=Path(__file__).resolve().parents[1];E=W/'evidence';T=W/'temp';S=W/'worktree'
identity=json.loads(subprocess.check_output(['python3',str(S/'scripts/git_identity.py'),'--root',str(S),'inspect','HEAD']))
assert identity['source_commit']==json.loads((E/'plan.json').read_text())['source_commit']
(E/'reproduction-source.json').write_text(json.dumps(identity,indent=2))
shutil.copytree(E/'harness',T/'maria',dirs_exist_ok=True)
p=T/'maria/go.mod';p.write_text(p.read_text().replace('<PRODUCT_WORKTREE>',str(S)))
bindings=json.loads((E/'bindings.json').read_text());over={}
for rel,indexes in [('internal/generatedgo/code/p1/p1_pure.go',range(5)),('internal/generatedgo/code/base/base.go',range(5,7))]:
 p=S/rel;s=p.read_text();a=0;b=len(s)
 if 'p1_pure' in rel:a=s.index('func Fn267(');b=s.index('\nfunc ',a+1)
 part=s[a:b]
 for i in indexes:
  r=bindings[i];assert part.count(r['old'])==r['matches'];part=part.replace(r['old'],r['new'])
 out=T/('overlay-'+rel.replace('/','_'));out.write_text(s[:a]+part+s[b:]);over[str(p)]=str(out)
for rel in ['internal/generatedgo/code/base/experiment_stages.go','experiment_stages.go']:
 name='overlay-'+rel.replace('/','_');shutil.copy(E/name,T/name);over[str(S/rel)]=str(T/name)
for a,b in over.items():assert hashlib.sha256(Path(b).read_bytes()).hexdigest()==json.loads((E/'preserved-hashes.json').read_text())[str(Path(a).relative_to(S))]
(E/'overlay.json').write_text(json.dumps({'Replace':over},indent=2));print('RESTORED identical overlay')
