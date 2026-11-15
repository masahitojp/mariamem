import importlib.util,json,subprocess,sys
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'close-evaluation/campaign.py'
s=importlib.util.spec_from_file_location('campaign',p);c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
identity=json.loads(subprocess.check_output([sys.executable,'scripts/git_identity.py','inspect','HEAD'],cwd=c.ROOT,text=True))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=c.ROOT)
(c.EVIDENCE/'identity.json').write_text(json.dumps(identity,indent=2))
c.checked(['go','test','-c','-p','1','-tags=closeeval','-o',str(c.TEMP/'stop.test'),'.'],'build.txt')
(c.EVIDENCE/'binary.json').write_text(json.dumps({'sha256':c.sha(c.TEMP/'stop.test'),'buildinfo':subprocess.check_output(['go','version','-m',str(c.TEMP/'stop.test')],env=c.ENV,text=True)},indent=2))
for p,cap in [(1,2),(2,4)]:
 c.trial(c.TEMP/'stop.test',p,cap,'sync','warmup')
for rep in range(3):
 for p,cap in [(1,2),(2,4)]: c.trial(c.TEMP/'stop.test',p,cap,'sync','diagnostic',rep)
