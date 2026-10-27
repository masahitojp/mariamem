from pathlib import Path
import ast,base64,hashlib,io,json,re,subprocess,xml.etree.ElementTree as ET,zipfile
TASK=Path(__file__).parent
SHA='6edcd29e65d3a669d5be6520abf6be2e61fa3445'
meta=json.loads((TASK/'artifacts.json').read_text());run=json.loads((TASK/'run.json').read_text());jobs=json.loads((TASK/'jobs.json').read_text())['jobs']
assert run['head_sha']==SHA and run['status']=='completed' and run['conclusion']=='success'
assert len(jobs)==4 and all(j['head_sha']==SHA and j['conclusion']=='success' for j in jobs)
assert all(a['workflow_run']['id']==run['id'] and a['workflow_run']['head_sha']==SHA for a in meta['artifacts'])
assert subprocess.check_output(['git','cat-file','-t',SHA],text=True).strip()=='commit'
def source(path):return subprocess.check_output(['git','show',SHA+':'+path],text=True)
def function(path,name,extra=None):
 tree=ast.parse(source(path));node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name);ns={} if extra is None else dict(extra);exec(compile(ast.Module(body=[node],type_ignores=[]),path,'exec'),ns);return ns[name]
assess=function('tests/live_acceptance/run.py','assess')
native_assess=function('tests/e2e_native_control/run.py','assess')
require=function('tests/dump_import_acceptance/linux_acquisition.py','require')
validate_acquisition=function('tests/dump_import_acceptance/linux_acquisition.py','validate',dict(require=require,re=re))
pin=json.loads(source('tests/dump_import_acceptance/linux-native-pin.json'))
variant_pin=json.loads(source('tests/live_acceptance/input-manifest.json'))['files']['tests/live_acceptance/goapp/main.go']
archives={};members={}
for artifact in meta['artifacts']:
 p=TASK/(str(artifact['id'])+'.zip.base64');raw=base64.decodebytes(p.read_bytes());assert artifact['digest']=='sha256:'+hashlib.sha256(raw).hexdigest()
 z=zipfile.ZipFile(io.BytesIO(raw));assert z.testzip() is None;archives[artifact['name']]=z
 members[str(artifact['id'])]={n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if not n.endswith('/')}
def read(z,name):return json.loads(z.read(name))
def parsed(z,prefix):
 events=[json.loads(line) for line in z.read(prefix+'/events.jsonl').decode().splitlines()]
 xml=ET.fromstring(z.read(prefix+'/pytest.xml'));counts={k:sum(int(s.get(k,0)) for s in xml.findall('.//testsuite')) for k in ['tests','errors','failures','skipped']}
 failures=[dict(name=c.get('name'),message=f.get('message','')) for c in xml.findall('.//testcase') for f in c.findall('failure')]
 return events,counts,failures
native={};assessment={'source_commit':SHA,'run_id':run['id'],'url':run['html_url'],'result':'PASS_CI_BOUND_LIVE_CANDIDATE','jobs':[dict(id=j['id'],name=j['name'],conclusion=j['conclusion']) for j in jobs],'native':{},'matrix':[],'installed':{},'qualification_or_release':False}
for version in ['3.11','3.14']:
 z=archives['live-native-py'+version+'-'+SHA];r=read(z,'reference/result.json');a=read(z,'acquisition/result.json');probe=read(z,'acquisition/producer-probe.json');observed=read(z,'acquisition/observed.json');variant=read(z,'reference/app-variant.json')
 assert r['source_commit']==a['source_commit']==variant['source_commit']==SHA
 assert r['result']=='PASS_NATIVE_CONTROL' and a['result']=='PASS' and probe['result']=='PASS'
 assert str(probe['schema_count_after']).strip()=='0' and not a['application_dump_generated'] and not a['dump_imported'] and not a['reader_executed']
 validate_acquisition(observed,pin,SHA)
 assert variant['source_sha256']==variant_pin and variant['binary_sha256']==r['go_app_sha256'] and variant['result']=='PASS_NATIVE_VARIANT'
 for kind in ['python','go']:
  es,counts,failures=parsed(z,'reference/'+kind);assert r['runs'][kind]['counts']==counts
  assert native_assess(kind,r['runs'][kind]['exit_code'],counts,es,failures)
 native[version]=(r,variant)
 assessment['native'][version]=dict(result='PASS_NATIVE_CONTROL_AND_ACQUISITION',python=r['python'].split()[0],source_commit=SHA,variant_source_sha256=variant_pin)
for platform,system,machine in [('macos-15','Darwin','arm64'),('ubuntu-24.04','Linux','x86_64')]:
 z=archives['live-host-'+platform+'-'+SHA]
 canonical=z.read('check.txt').decode();assert '1040 passed, 45 skipped' in canonical and '76 subtests passed' in canonical
 race=z.read('live-race.txt').decode();assert all('github.com/masahitojp/mariamem/'+p in race for p in ['internal/live','internal/control']) and re.search(r'ok\s+github.com/masahitojp/mariamem\s',race)
 assert 'PASS: Go prepared / Python normal controls and exact accepted-exception tripwires' in z.read('integration.txt').decode()
 for version in ['3.11','3.14']:
  assert '53 passed' in z.read('py'+version+'-unit.txt').decode()
  outcomes=[]
  for scenario,mutation in [('positive',None),('skip-reset','skip-reset'),('restart-app','restart-app')]:
   prefix='py'+version+'/'+scenario;r=read(z,prefix+'/result.json')
   assert r['source_commit']==SHA and r['platform']['system']==system and r['platform']['machine']==machine
   assert r['result']==('PASS_PUBLIC_LIVE' if mutation is None else 'MUTATION_DETECTED')
   assert r['native_reference']==native[version][0] and r['native_variant']==native[version][1]
   for build in r['binary_buildinfo'].values():assert 'vcs.revision='+SHA in build and 'vcs.modified=false' in build and 'go1.26.10' in build
   for kind in ['python','go-live','go-fork']:
    es,counts,failures=parsed(z,prefix+'/'+kind);entry=r['runs'][kind];assert counts==entry['counts']
    effective=mutation if kind!='go-fork' else None
    reference=r['prior_native_reference']['observation']['python' if kind=='python' else 'go']
    assert assess(kind,entry['exit_code'],counts,es,failures,reference,effective),(platform,version,scenario,kind)
   es,counts,_=parsed(z,prefix+'/live-controls');assert counts==dict(tests=4,errors=0,failures=0,skipped=0)
   get=lambda name:[e for e in es if e['event']==name]
   assert len(get('guest_host_cleanup'))==4 and all(e['reaped'] and e['directory_removed'] for e in get('guest_host_cleanup'))
   busy=get('busy_control_pass');assert len(busy)==2 and {e['transaction'] for e in busy}=={True,False} and all(e['new_handshake_refused'] and e['old_data_preserved'] and e['busy_code']=='busy' for e in busy)
   parent=get('parent_lifetime_control_pass');assert len(parent)==1 and parent[0]['old_child_preserved'] and parent[0]['reset_refused']
   fault=get('failed_replace_control_pass');assert len(fault)==1 and all(fault[0][k] for k in ['no_admission','explicit_retry','original_cause_retained','old_endpoint_closed'])
   outcomes.append(dict(scenario=scenario,result=r['result'],live_languages=['python','go'],go_fork_control='PASS',real_controls=4))
  assessment['matrix'].append(dict(host=platform,architecture=machine,python=r['python'].split()[0],focused_tests_passed=53,canonical_check='1040 passed/45 explicit skips/76 subtest passes',runtime_integration='PASS by successful exact-source CI step; raw output retained',live_core_race='PASS',campaigns=outcomes))
 installed=read(z,'installed/result.json');assert installed['source_commit']==SHA and installed['result']=='PASS_INSTALLED_LIVE'
 py=installed['python'];go=installed['go'];assert py['result']=='PASS_INSTALLED_PYTHON_LIVE' and all(py[k] for k in ['source_consumed','host_reaped','directory_removed']) and '/site-packages/mariamem/__init__.py' in py['module']
 assert go['result']=='PASS_EXTERNAL_GO_LIVE' and all(go[k] for k in ['busy_refused','closed_parent_refused','source_consumed']) and go['sum_after_reset']==1
 assessment['installed'][platform]=dict(python='PASS_INSTALLED_PYTHON_LIVE',python_version_scope='default3.14 interpreter only',go='PASS_EXTERNAL_GO_LIVE with exact local source replacement',wheel_sha256=installed['wheel_sha256'])
assessment['counts']={'native_application_controls':4,'public_live_positive_routes':8,'actual_lifecycle_defects_detected':16,'go_fork_control_campaigns':12,'real_control_tests':48,'focused_tests_passed':212}
assessment['not_claimed']=['main adoption','Qualification/release','physical SQL session continuity','application job fencing','automatic pool retirement','parallel tests sharing one Live','broad Django adapter compatibility','cold/setup/performance improvement']
(TASK/'assessment.json').write_text(json.dumps(assessment,indent=2)+'\n');(TASK/'artifact-members.json').write_text(json.dumps(members,indent=2)+'\n')
print(json.dumps(dict(result=assessment['result'],source_commit=SHA,counts=assessment['counts'])))
