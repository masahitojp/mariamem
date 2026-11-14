from pathlib import Path
import subprocess,tarfile,io,json,shutil
W=Path.cwd()/'build/experiment-work/response-ipc';T=W/'temp';E=W/'evidence'
data=subprocess.check_output(['git','archive','f26e3154','benchmarks/sample-guest-cost/results-20261114/harness/maria-suite'])
with tarfile.open(fileobj=io.BytesIO(data))as a:
 prefix='benchmarks/sample-guest-cost/results-20261114/harness/maria-suite/'
 for m in a.getmembers():
  if m.isfile():
   p=T/'maria'/m.name[len(prefix):];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(a.extractfile(m).read())
p=T/'maria/go.mod';p.write_text(p.read_text().replace('<PRODUCT_WORKTREE>',str(W/'worktree')))
shutil.copy('build/experiment-work/modelcase-default-ipc/evidence/ipc_overlay.py',E/'ipc_overlay.py')
subprocess.run(['python3',str(E/'ipc_overlay.py')],check=True)
s=(T/'linked_overlay.go').read_text();assert 'ledger=&ipcLedger' in s
subprocess.run(['python3','scripts/git_identity.py','--root',str(W/'worktree'),'inspect','HEAD'],stdout=(E/'source.json').open('w'),check=True)
(E/'plan.json').write_text(json.dumps({'source_commit':'bb1e937ae75b5788c8548a52987d9d42f78292d5','harness':'f26e3154','sql':'REVENUE_PREAGG=1','counts':'3 observer-on plus 3 off alternating P8; no retries/removals','budget_gib':8,'min_free_gib':8,'build_timeout':1200,'process_timeout':180,'scope':'observation only; no buffering or transport replacement'},indent=2))
shutil.copy('/private/tmp/setup-response-ipc.py',E/'setup.py')
