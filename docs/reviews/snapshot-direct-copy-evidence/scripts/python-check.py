from pathlib import Path
import json,os,subprocess,sys,time
w=Path(__file__).resolve().parents[1]; repo=w/'temp/source'
env=dict(os.environ,PYTHONPATH=str(repo/'python'),MARIAMEM_TEST_HOST=str(w/'temp/mariamem-host'),
         MARIAMEM_SNAPSHOT_DIRECT='1',GOMAXPROCS='2',TMPDIR=str(w/'temp/tmp'))
cmd=[str(w/'temp/venv/bin/python'),'-m','pytest','tests/test_owned_snapshot.py','-k','created_temporary or modified_child or import_owns','-q']
start=time.monotonic()
with (w/'evidence/python-owned.log').open('w') as log:
    r=subprocess.run(cmd,cwd=repo,env=env,stdout=log,stderr=subprocess.STDOUT)
(w/'evidence/python-check.json').write_text(json.dumps(dict(command=cmd,returncode=r.returncode,
    seconds=time.monotonic()-start,scope='unchanged Python export/import route regression; no direct-copy speedup claim',
    python=subprocess.check_output([str(w/'temp/venv/bin/python'),'--version'],text=True).strip(),
    packages=subprocess.check_output([str(w/'temp/venv/bin/python'),'-m','pip','freeze'],text=True)),indent=2)+'\n')
print((w/'evidence/python-owned.log').read_text(),flush=True)
sys.exit(r.returncode)
