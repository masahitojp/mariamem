from pathlib import Path
import subprocess,tarfile,io,json,shutil
W=Path.cwd()/'build/experiment-work/response-buffer';T=W/'temp';E=W/'evidence'
data=subprocess.check_output(['git','archive','918fb708','benchmarks/response-ipc/results-20261114/harness'])
with tarfile.open(fileobj=io.BytesIO(data))as a:
 prefix='benchmarks/response-ipc/results-20261114/harness/'
 for m in a.getmembers():
  if m.isfile():
   p=T/'maria'/m.name[len(prefix):];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(a.extractfile(m).read())
p=T/'maria/go.mod';p.write_text(p.read_text().replace('<PRODUCT_WORKTREE>',str(W/'worktree')))
p=T/'maria/store/fixture_test.go';s=p.read_text().replace('"sync"','"sync"\n "sync/atomic"');s=s.replace('var fx *fixture','var closeErrors atomic.Int64\nfunc checkedClose(err error){if err!=nil {fmt.Fprintln(os.Stderr,"CLOSE ERROR:",err);closeErrors.Add(1)}}\nvar fx *fixture')
import re
s=re.sub(r'\b(fx.sharedDB|db|s|snap|srv)\.Close\(\)',r'checkedClose(\1.Close())',s)
s=s.replace('fx.close()','fx.close()\n if closeErrors.Load()!=0 {code=1}')
p.write_text(s)
old=Path('build/experiment-work/response-ipc/evidence/ipc_overlay.py');shutil.copy(old,E/'ipc_overlay.py');subprocess.run(['python3',str(E/'ipc_overlay.py')],check=True)
p=W/'worktree/internal/guest/guest.go';s=p.read_text().replace('"context"','"context"\n "bufio"');s=s.replace('func (p *Process) read() {','var experimentReadBuffer = os.Getenv("MARIAMEM_EXPERIMENT_READ_BUFFER")=="1"\nfunc (p *Process) read() {\n var input io.Reader=p.out\n if experimentReadBuffer {input=bufio.NewReaderSize(p.out,4096)}');assert s.count('io.ReadFull(p.out,')==2;s=s.replace('io.ReadFull(p.out,','io.ReadFull(input,');(T/'guest_overlay.go').write_text(s)
over=json.loads((E/'overlay.json').read_text());over['Replace'][str(p)]=str(T/'guest_overlay.go');over['Replace'][str(W/'worktree/internal/guest/experiment_buffer_test.go')]=str(T/'experiment_buffer_test.go');(E/'overlay.json').write_text(json.dumps(over,indent=2))
shutil.copy('/private/tmp/setup-buffer185.py',E/'setup.py')
(E/'plan.json').write_text(json.dumps({'source_commit':'bb1e937ae75b5788c8548a52987d9d42f78292d5','candidate':'same binary static experiment flag; host 4096 byte reader only','harness':'918fb708 plus checked public Close errors','sql':'REVENUE_PREAGG=1','plain':{'parallel':[1,8],'warmup_per_arm_per_parallel':1,'measured_pairs_per_parallel':5},'observer':{'parallel':8,'pairs':3,'location':'underlying os.Pipe before buffered reader'},'budget_gib':8,'min_free_gib':8,'build_timeout_s':1200,'process_timeout_s':180,'stop':'fixed campaign; failures preserved; no additional favorable repeats'},indent=2))
