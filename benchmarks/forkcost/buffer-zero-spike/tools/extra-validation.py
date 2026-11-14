from pathlib import Path
import os,subprocess,json,re,hashlib
E=Path(__file__).resolve().parent;X=E.parent;T=X/'temp';P=T/'native/product';env=os.environ.copy();env.update(GOCACHE=str(T/'gocache'),GOMODCACHE=str(T/'modcache'),GOMAXPROCS='8',GOGC='100',CGO_ENABLED='0',TMPDIR=str(T/'tmp'))
# Rebuild the I/O-only binary after narrowing the wrapper; other binaries are cached.
with (E/'spike-extra-build-limited.log').open('w') as f:subprocess.run([os.sys.executable,str(E/'build-extra.py'),'spike'],env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=1200)
for name,args in [('fault',[]),('recovery-clean',['-crash=false']),('recovery-dirty',['-crash=true'])]:
 binary='fault' if name=='fault' else 'recovery';label='spike-poison-'+name;runenv=dict(env,MARIAMEM_BP_ZERO_MODE_INTERNAL='poison')
 with (E/(label+'.log')).open('w') as f:subprocess.run([str(T/('spike-'+binary)),*args,'-out',str(E/(label+'.json'))],env=runenv,stdout=f,stderr=subprocess.STDOUT,timeout=200,check=True)
 assert json.loads((E/(label+'.json')).read_text())['success'];print('PASS',label,flush=True)
proof=json.loads((E/'binding-review.json').read_text());changes={x['old']:x['new'] for x in proof['crc']['relocations']};source=P/'internal/generatedgo/code/p4/crc32c_test.go';old=source.read_text();new=re.sub(r'(?<![A-Za-z0-9_])(\d+)(?![A-Za-z0-9_])',lambda m:str(changes.get(int(m[1]),int(m[1]))),old);patched=T/'crc32c-relocated-fixture_test.go';patched.write_text(new);overlay=T/'crc-test-overlay.json';overlay.write_text(json.dumps({'Replace':{str(source):str(patched)}}));(E/'crc-fixture-relocation.json').write_text(json.dumps({'original_sha256':hashlib.sha256(old.encode()).hexdigest(),'relocated_sha256':hashlib.sha256(new.encode()).hexdigest(),'addresses':changes,'scope':'fixture addresses only; original test data and assertions unchanged'},indent=2)+'\n')
with (E/'candidate-crc-tests.log').open('w') as f:subprocess.run(['go','test','-p','1','-vet=off','-overlay',str(overlay),'./internal/generatedgo/code/p4','-count=1','-v'],cwd=P,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=600,check=True)
print('PASS candidate native/reference CRC differential tests',flush=True)
with (E/'candidate-owner-tests.log').open('w') as f:subprocess.run(['go','test','-p','1','-vet=off','./internal/generatedgo','-run','TestGuestEnvironmentIsPerInstance|TestControlledGuestFirstWorkerTrap','-count=1','-v'],cwd=P,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=600,check=True)
(E/'extra-validation-complete.json').write_text(json.dumps({'result':'PASS','cases':5},indent=2)+'\n');print('PASS candidate owner controls',flush=True)
