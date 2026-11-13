from pathlib import Path
import os,subprocess,json,hashlib
r=Path(__file__).resolve().parents[1];env=os.environ.copy();env.update(GOCACHE=str(r/'temp/gocache'),GOMODCACHE=str(r/'temp/modcache'),CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();before=sha(r/'temp/harness/main.go');bins={}
for mode in ['canonical','observed']:
 cmd=['go','build'];cmd+=['-overlay',str(r/'temp/overlay/overlay.json')] if mode=='observed' else [];cmd+=['-o',str(r/'temp'/mode),'.'];print('building '+mode,flush=True);subprocess.run(cmd,cwd=r/'temp/harness',env=env,check=True);bins[mode]=sha(r/'temp'/mode)
assert before==sha(r/'temp/harness/main.go');(r/'evidence/binary-hashes.json').write_text(json.dumps(bins,indent=2));(r/'evidence/buildinfo.txt').write_text(subprocess.check_output(['go','version','-m',str(r/'temp/canonical')],text=True));(r/'evidence/overlay-hashes.json').write_bytes((r/'temp/overlay/hashes.json').read_bytes())
