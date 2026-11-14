from pathlib import Path
import json,subprocess,os,hashlib,shutil,sys
E=Path(__file__).resolve().parent;X=E.parent;W=X/'worktree';T=X/'temp'
assert json.loads((E/'measurement-complete.json').read_text())['result']=='PASS'
g=json.loads((T/'guest/guest.json').read_text());dev=json.loads((T/'native/installation-inputs.json').read_text());proof=json.loads((E/'binding-review.json').read_text());new=g['guest_sha256'];old=json.loads((W/'release/generated-go-inputs.json').read_text())['guest_sha256']
assert proof['result']=='PASS_IDENTICAL_WORKER_CRC_BINDING' and proof['guest_sha256']==new
assert not proof['crc']['relocations'] and proof['crc']['delta']==0
if sys.argv[1]=='prepare':
 # Remove the temporary exact-development identity clause; the canonical input
 # now receives the reviewed candidate SHA. Body/table oracles remain exact.
 p=W/'scripts/generate_runtime.py';s=p.read_text();a=s.index('    # Explicit development-only identity;');b=s.index('    from runtime_thread_lifetime import validate_inputs',a);p.write_text(s[:a]+s[b:])
 for name in ('runtime_thread_lifetime.py','runtime_crc32c.py'):
  p=W/'scripts'/name;s=p.read_text();assert s.count(old)==1;p.write_text(s.replace(old,new))
 p=W/'release/generated-go-inputs.json';v=json.loads(p.read_text());v.update(guest_sha256=new,source_sha=g['source_commit'],candidate_files_sha256=dev['candidate_files_sha256'],data_sha256=dev['data_sha256']);p.write_text(json.dumps(v,indent=2)+'\n')
 p=W/'release/generated-go-translation.json';v=json.loads((T/'native/translation/input-manifest.json').read_text());p.write_text(json.dumps(v,indent=2)+'\n')
 p=W/'release/generated-go-build.json';previous=json.loads(p.read_text());(E/'previous-canonical-build.json').write_bytes(p.read_bytes());v=dict(previous);v.update(guest_sha256=new,source_commit=g['source_commit'],guest_size=g['guest_bytes'],linked_guest_sha256=g['repetitions'][0]['linked_sha256'],repetitions=1,completed=False,full_guest_regeneration='PENDING',prepared_source=g['prepared_source'],toolchain=g['toolchain']);v['compiled_guest_source_scope']+='; buffer-pool descriptor-only initial zeroing with unchanged common allocator, extent alignment, default16MiB and grow behavior';v['ci_evidence']={'status':'PENDING_INDEPENDENT_CANONICAL_REGENERATION','bootstrap_receipt':'docs/reviews/buffer-zero-candidate/build-evidence/guest.json.gz'};v['incoming_guest_origin']={'source_commit':g['source_commit'],'contract':'development-unqualified-v1','independent_source_builds':1,'use':'Single-build source bootstrap; not qualification or a relabeled canonical CI PASS.'};v['previous_canonical_evidence']={'guest_sha256':old,'record':'docs/reviews/buffer-zero-candidate/build-evidence/previous-canonical-build.json','record_sha256':hashlib.sha256((E/'previous-canonical-build.json').read_bytes()).hexdigest(),'source_commit':previous['source_commit'],'ci_evidence':previous.get('ci_evidence')};p.write_text(json.dumps(v,indent=2)+'\n')
 p=W/'internal/runtimekind/kind.go';s=p.read_text();assert s.count(old)==1;p.write_text(s.replace(old,new))
 p=W/'tests/fixtures/routine-thread-layout.json';v=json.loads(p.read_text());assert v['guest_sha256']==old;v['guest_sha256']=new;v['result']='Candidate unchanged data/worker layout; exact runtime controls remain required';p.write_text(json.dumps(v,indent=2)+'\n')
 p=W/'tests/fixtures/prepared-p2-binding/identity.json';v=json.loads(p.read_text());v['prior_prepared_output_guest_sha256']=old;p.write_text(json.dumps(v,indent=2)+'\n')
 p=W/'tests/test_thread_lifetime_binding.py';s=p.read_text().replace("'prior_dictionary_guest_sha256'])", "'prior_dictionary_guest_sha256', 'prior_prepared_output_guest_sha256'])");p.write_text(s)
 sys.exit(0)
assert sys.argv[1]=='generate'
output=T/'canonical-generated';env=dict(os.environ,GOCACHE=str(T/'gocache'),GOMODCACHE=str(T/'modcache'),CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100',TMPDIR=str(T/'tmp'))
subprocess.run([str(T/'venv/bin/python'),str(W/'scripts/generate_runtime.py'),'--source-module',str(T/'native/candidate/module'),'--output',str(output)],env=env,check=True)
# Check that formalization changes provenance only, not the executed Go bytes.
a=T/'native/product/internal/generatedgo';same=[]
for f in output.rglob('*'):
 if f.is_file() and f.suffix in ('.go','.s'):
  n=f.relative_to(output);assert f.read_bytes()==(a/n).read_bytes(),str(n);same.append(str(n))
assert (W/'internal/runtimekind/kind.go').read_bytes()==(T/'native/product/internal/runtimekind/kind.go').read_bytes()
(E/'canonical-to-measured-runtime-equivalence.json').write_text(json.dumps({'result':'PASS_IDENTICAL_GO_AND_ASSEMBLY','files':same,'note':'canonical provenance differs from UNQUALIFIED bootstrap; no execution receipt relabeled'},indent=2)+'\n')
# Copy deterministic generator output, never edit generated bodies.
for f in output.rglob('*'):
 if f.is_file():
  target=W/'internal/generatedgo'/f.relative_to(output);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target)
print('Canonical candidate installed; independent reproduction and platform CI PENDING')
