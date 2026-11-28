import hashlib,io,json,os,pathlib,subprocess,sys,tarfile
B=pathlib.Path(os.environ.get('WAIT_NOTIFY_WORKSPACE',str(pathlib.Path(__file__).resolve().parent.parent))).resolve(); T=B/'temp'; E=B/'evidence'; R=B/'worktree'
sys.path.insert(0,str(R/'scripts'))
from git_identity import require_commit
S='e00b3ec41f9c5d4ca3f85db4ff73198dbf3613e9'
H='1977fff480c2f976bc23f4d2e1b8ff8db36ad128'
arm=sys.argv[1]; assert arm in ('control','candidate')
require_commit(R,S);require_commit(R,H)
def extract(commit,path,out):
 data=subprocess.check_output(['git','archive',commit]+([path] if path else []),cwd=R)
 out.mkdir(parents=True,exist_ok=False)
 tarfile.open(fileobj=io.BytesIO(data)).extractall(out,filter='data')
 return hashlib.sha256(data).hexdigest()
src=T/'control-source' if arm=='control' else T/'dev/product'
record={'baseline_source_commit':S,'harness_source_commit':H,'arm':arm}
if arm=='control': record['source_archive_sha256']=extract(S,None,src)
else:
 dev=json.loads((T/'dev/development.json').read_text()); assert dev['smoke']=='PASS'
 record.update(guest_sha256=dev['guest_sha256'],guest_source_commit=dev['source_identity']['source_commit'] if 'source_commit' in dev['source_identity'] else dev['source_identity'].get('commit'))
dest=T/('harness-'+arm)
record['harness_archive_sha256']=extract(H,'benchmarks/comparison-variance/harness/maria-suite',dest)
suite=dest/'benchmarks/comparison-variance/harness/maria-suite'
record['harness_files_sha256']={str(p.relative_to(suite)):hashlib.sha256(p.read_bytes()).hexdigest() for p in suite.rglob('*') if p.is_file()}
p=suite/'go.mod';p.write_text(p.read_text().replace('<MARIAMEM_SOURCE>',str(src)))
env=dict(os.environ,GOTOOLCHAIN='go1.27.4',CGO_ENABLED='0',GOMAXPROCS='8',GOWORK='off',GOENV='off',GOCACHE=str(T/'gocache'),GOPATH=str(T/'gopath'),GOMODCACHE=str(T/'modcache'))
subprocess.run(['go','mod','tidy'],cwd=suite,env=env,check=True,timeout=300)
binary=T/(arm+'.test')
subprocess.run(['go','test','-c','-p','1','-o',str(binary),'./store'],cwd=suite,env=env,check=True,timeout=1200)
record.update(binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),buildinfo=subprocess.check_output(['go','version','-m',str(binary)],env=env,text=True),go_mod=p.read_text(),go_sum_sha256=hashlib.sha256((suite/'go.sum').read_bytes()).hexdigest())
assert 'go1.27.4' in record['buildinfo'] and 'CGO_ENABLED=0' in record['buildinfo']
(E/('build-'+arm+'.json')).write_text(json.dumps(record,indent=2)+'\n')
print('BUILD PASS',arm,flush=True)
