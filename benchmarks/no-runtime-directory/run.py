import importlib.util,json,os,subprocess,sys
from pathlib import Path
s=importlib.util.spec_from_file_location('campaign',Path(__file__).resolve().parents[1]/'close-evaluation/campaign.py');c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
c.ENV['GOCACHE']=str(c.ROOT.parents[1]/'close-stop-cost/temp/go-cache')
# Borrow only the inactive paused diagnostic's cache; no old executable is used.
assert Path(c.ENV['GOCACHE']).is_dir(),c.ENV['GOCACHE']
identity=json.loads(subprocess.check_output([sys.executable,'scripts/git_identity.py','inspect','HEAD'],cwd=c.ROOT,text=True));assert not subprocess.check_output(['git','status','--porcelain'],cwd=c.ROOT)
base=subprocess.check_output(['git','show','c680bfe9:mariamem.go'],cwd=c.ROOT)
(c.TEMP/'baseline.go').write_bytes(base)
(c.TEMP/'overlay.json').write_text(json.dumps({'Replace':{str(c.ROOT/'mariamem.go'):str(c.TEMP/'baseline.go')}}))
(c.EVIDENCE/'inputs.json').write_text(json.dumps(identity,indent=2))
c.checked(['go','test','-p','1','.','./mariamemtest','./internal/host'],'tests.txt')
c.checked(['go','test','-p','1','-tags=integration','./tests/generatedmemory','-run','TestPureMemory32|TestProcessImageSurvivesIndependentRootsAndSnapshots','-count=1'],'guest.txt')
c.checked([sys.executable,'scripts/check_public.py'],'public.txt')
for arm in ['baseline','candidate']:
 args=['go','test','-c','-p','1','-tags=closeeval','-o',str(c.TEMP/(arm+'.test'))]
 if arm=='baseline':args+=['-overlay',str(c.TEMP/'overlay.json')]
 c.checked(args+['.'],'build-'+arm+'.txt')
(c.EVIDENCE/'binaries.json').write_text(json.dumps({a:{'sha256':c.sha(c.TEMP/(a+'.test')),'bytes':(c.TEMP/(a+'.test')).stat().st_size,'buildinfo':subprocess.check_output(['go','version','-m',str(c.TEMP/(a+'.test'))],env=c.ENV,text=True)} for a in ['baseline','candidate']},indent=2))
for phase,n in [('warmup',1),('measure',3)]:
 for rep in range(n):
  for p,cap in [(1,1),(1,2),(2,2),(2,4)]:
   for arm in (['baseline','candidate'] if rep%2==0 else ['candidate','baseline']):
    r=c.trial(c.TEMP/(arm+'.test'),p,cap,'sync',phase+'-'+arm,rep)
    assert r['runtime_directory_count']==(48 if arm=='baseline' else 0),r
