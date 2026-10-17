#!/usr/bin/env python3
"""Isolated per-call before-OwnRoot injection; no production hook is installed."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from check import ROOT,GO,environment,modules,clean
w=Path(sys.argv[1]).resolve();env=environment(w);modules(env)
identity=json.loads(subprocess.check_output([sys.executable,'scripts/git_identity.py','inspect','HEAD'],cwd=ROOT))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT).strip()
out=w/'evidence/corruption';out.mkdir(exist_ok=True)
source=ROOT/'internal/host/heap_snapshot.go';original=source.read_text()
text=original.replace('"context"','"context"\n "github.com/masahitojp/mariamem/internal/prepared"')
needle='owned, e := snapshot.OwnRoot(image, s.build)'
assert text.count(needle)==1
text=text.replace(needle,'if e := prepared.ProbeBeforeOwn(ctx, image); e != nil { return nil, true, e }\n\t'+needle)
overlay=w/'temp/corruption-host.go';overlay.write_text(text)
mapping=w/'temp/corruption-overlay.json';mapping.write_text(json.dumps({'Replace':{str(source):str(overlay)}}))
(out/'overlay.go.txt').write_text(text)
env['OWNED_ROOT_PROBE_EVIDENCE']=str(out)
cmd=[str(GO),'test','-json','-p','1','-tags=integration,ownedroot_probe','-overlay',str(mapping),'./tests/gointegration','-run','^TestOwnedRootCorruptionProbe$','-count=1','-timeout=120s']
r=subprocess.run(cmd,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=180)
(out/'runner.txt').write_text(clean(r.stdout,w))
(out/'receipt.json').write_text(json.dumps(dict(source_commit=identity['source_commit'],exit_code=r.returncode,original_sha256=hashlib.sha256(original.encode()).hexdigest(),overlay_sha256=hashlib.sha256(text.encode()).hexdigest(),injection_point='after TakeRoot; before OwnRoot; capture not yet returned',arguments=[clean(v,w) for v in cmd]),indent=2)+'\n')
print(r.stdout[-5000:]);sys.exit(r.returncode)
