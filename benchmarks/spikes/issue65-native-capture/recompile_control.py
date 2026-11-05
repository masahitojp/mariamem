"""Add one scoped regression control; preserve complete staged/binary identity."""
import os,sys,json,subprocess,hashlib,shutil
from pathlib import Path
w=Path('.').resolve();r=w/'worktree';sys.path.insert(0,str(r/'scripts'));from build_feedback import go_environment
from dev_guest import source_identity,inventory,verify_guest
from common import digest
os.environ['MARIAMEM_DEV_WORKSPACE']=str(w);env=go_environment({k:v for k,v in os.environ.items() if k not in ('GOCACHE','GOPATH','GOMODCACHE')});env.update(GOTOOLCHAIN='go1.26.10',CGO_ENABLED='0',GOWORK='off',GOENV='off',GOMAXPROCS='2',GOGC='50')
origin=source_identity(r);guest=verify_guest(r,w/'temp/artifact');prior=json.loads((w/'evidence/host-build.json').read_text());product=w/'temp/host/product';assert inventory(product)==prior['source_inventory'];assert digest(w/'temp/host/wire.test')==prior['binary_sha256']
shutil.copy2(w/'temp/tools/capture_test.go.txt',product/'cmd/issue65-wire/capture_test.go');pins=inventory(product);changed=[n for n in pins if pins[n]!=prior['source_inventory'][n]];assert changed==['cmd/issue65-wire/capture_test.go'],changed
fixed={p.name:digest(p) for p in (w/'temp/tools').glob('*.txt')};selfpin=digest(Path(__file__))
subprocess.run(['go','test','-c','-p','1','-trimpath','-buildvcs=false','-o',str(w/'temp/host/wire.test'),'./cmd/issue65-wire'],cwd=product,env=env,check=True)
assert inventory(product)==pins and source_identity(r)==origin;assert {p.name:digest(p) for p in (w/'temp/tools').glob('*.txt')}==fixed;assert digest(Path(__file__))==selfpin
record={'contract':'issue65-native-capture-prototype-unqualified','guest_sha256':guest['guest_sha256'],'guest_source_commit':guest['source_commit'],'host_source_commit':origin['commit'],'source_inventory':pins,'prototype_templates_sha256':fixed,'binary_sha256':digest(w/'temp/host/wire.test'),'go_buildinfo':subprocess.check_output(['go','version','-m',str(w/'temp/host/wire.test')],env=env,text=True),'parent_host_record_sha256':digest(w/'evidence/host-build.json'),'changed_staged_files':changed,'assembler_sha256':selfpin}
(w/'evidence/host-build-final-control.json').write_text(json.dumps(record,indent=2)+'\n');print('Built immutable final test/control binary',record['binary_sha256'])
