import hashlib,json,os,subprocess,sys
from pathlib import Path
root=Path.cwd();task=root.parent;temp=task/'temp';evidence=task/'evidence'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,r):Path(p).write_text(json.dumps(r,indent=2)+'\n')
def run(name,args):
 print('PHASE',name,flush=True)
 with (evidence/(name+'.txt')).open('w') as out:subprocess.run([str(x) for x in args],cwd=root,env=env,stdout=out,stderr=subprocess.STDOUT,check=True)
env=dict(os.environ,GOCACHE=str(temp/'gocache'),GOTMPDIR=str(temp/'go-tmp'),GOTOOLCHAIN='go1.26.8',GOWORK='off',GOENV='off',GOFLAGS='',GOEXPERIMENT='',PYTHONDONTWRITEBYTECODE='1')
(temp/'go-tmp').mkdir(exist_ok=True)
run('identity',[sys.executable,'scripts/git_identity.py','inspect','HEAD'])
subprocess.run([sys.executable,'-m','venv',str(temp/'venv')],check=True)
py=temp/'venv/bin/python'
run('dependencies',[py,'-m','pip','install','pytest==8.4.2','PyMySQL==1.2.3','PyYAML==6.0.3','setuptools','wheel'])
run('source-tests',[py,'-m','pytest','-q','tests/test_prepared_source_patch.py','tests/test_prepared_time_patch.py','tests/test_prepared_param_order.py','tests/test_thread_lifetime_binding.py'])
run('prepare',[py,'scripts/prepare_guest.py'])
write(evidence/'prepared-source.json',json.loads((root/'build/prepared-source.json').read_text()))
guest=temp/'reviewed-guest/mariamem.wasm';record=json.loads((temp/'reviewed-guest/guest.json').read_text())
expected='8f6177627855232d096cfb3987d94e35c19fc4fc0c7f32ca8c69ff9fd4990a40'
assert sha(guest)==record['guest_sha256']==expected
sys.path.insert(0,str(root/'scripts'))
from build_generated_guest import download
tools=json.loads((root/'release/generated-go-toolchain.json').read_text())
converter=download(tools['archives']['converter'],root/'build/downloads')
spike=root/'benchmarks/spikes/generated-go-integration'
run('translation',[py,spike/'translate_guest.py','--guest',guest,'--guest-sha256',expected,'--converter-archive',converter,'--output',temp/'translation'])
raw=json.loads((temp/'translation/input-manifest.json').read_text());write(root/'release/generated-go-translation.json',raw)
run('adapter',[py,spike/'setup_candidate.py','--source-only','--source-module',temp/'translation/module','--guest',guest,'--input-manifest',temp/'translation/input-manifest.json','--output',temp/'candidate'])
module=temp/'candidate/module';pins=json.loads((root/'release/generated-go-inputs.json').read_text())
pins.update(guest_sha256=expected,source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),candidate_files_sha256={str(p.relative_to(module)):sha(p) for ext in ('*.go','*.s') for p in module.rglob(ext)},data_sha256=sha(module/'generated/data.bin'))
write(root/'release/generated-go-inputs.json',pins)
run('install',[py,'scripts/generate_runtime.py','--source-module',module,'--output',temp/'generatedgo'])
# Install only canonical-generator output; never hand-edit it.
shutil=__import__('shutil');shutil.rmtree(root/'internal/generatedgo');shutil.copytree(temp/'generatedgo',root/'internal/generatedgo')
run('canonical-inventory',[py,'scripts/verify_generated_runtime.py'])
run('compile',['go','build','-p','1','-trimpath','-o',temp/'mariamem-host','./cmd/mariamem-host'])
write(evidence/'local-generation.json',{'baseline_source_commit':pins['source_sha'],'guest_sha256':expected,'guest_origin_source_commit':record['source_identity']['commit'],'guest_origin_note':'Previous tested development guest used only to prepare generation; independent canonical source builds still required','generated_provenance_sha256':sha(root/'internal/generatedgo/provenance.json'),'host_sha256':sha(temp/'mariamem-host'),'result':'LOCAL GENERATION AND COMPILE PASS; P6 CI pending'})
print('PHASE complete',flush=True)
