"""Run from the experiment root with worktree at the pinned candidate."""
import json,os,subprocess,sys
from pathlib import Path
w=Path.cwd();root=w/'worktree';tmp=w/'temp';out=w/'evidence'
env=dict(os.environ,GOMAXPROCS='8',GOGC='100',GOPROXY='off',GOCACHE=str(tmp/'cache'),GOTMPDIR=str(tmp/'gotmp'))
for arm,sha in [('ring','a1ce4a7d568fbf6eac7bee032a7fdfbe464544fb'),('os','be12aeb6ebed61f291d98ffa08b872a03695900b')]:
    assert json.loads(subprocess.check_output(['python3',root/'scripts/git_identity.py','--root',root,'inspect',sha]))['source_commit']==sha
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()=='a1ce4a7d568fbf6eac7bee032a7fdfbe464544fb'
if sys.argv[1]=='build':
    source=root/'tests/gointegration/large_response_test.go'
    b=source.read_text().replace('"fmt"','"fmt"\n"os"\n"runtime/trace"')
    b=b.replace('before := cpuTime()', '''f,err:=os.Create(os.Getenv("TRACE")); if err!=nil {b.Fatal(err)}
    if err=trace.Start(f);err!=nil {b.Fatal(err)}
    before := cpuTime()''').replace('b.StopTimer()','b.StopTimer(); after:=cpuTime(); trace.Stop(); if err:=f.Close();err!=nil {b.Fatal(err)}').replace('float64(cpuTime()-before)','float64(after-before)')
    path=tmp/'bench.go';path.write_text(b)
    for arm in ('os','ring'):
        overlay={str(source):str(path)}
        if arm=='os':
            linked='internal/guest/linked.go';replacement=tmp/'os-linked.go'
            replacement.write_bytes(subprocess.check_output(['git','show','HEAD^:'+linked],cwd=root))
            overlay[str(root/linked)]=str(replacement)
        cfg=tmp/(arm+'.json');cfg.write_text(json.dumps({'Replace':overlay}))
        subprocess.run(['go','test','-c','-p','2','-vet=off','-trimpath','-tags=integration','-overlay',cfg,'-o',tmp/arm,'./tests/gointegration'],env=env,cwd=root,check=True)
elif sys.argv[1]=='run':
    for b in range(1,4):
        for arm in (('os','ring') if b%2 else ('ring','os')):
            name=f'{arm}-{b}';trace=out/(name+'.trace')
            assert not trace.exists()
            result=subprocess.run([tmp/arm,'-test.run=^$','-test.bench=^BenchmarkLargeResponseBatch$','-test.benchtime=1x'],env=dict(env,TRACE=str(trace)),text=True,capture_output=True,timeout=90)
            (out/(name+'.log')).write_text(result.stdout+result.stderr)
            assert result.returncode==0 and 'PASS' in result.stdout,result.stdout+result.stderr
    for trace in out.glob('*.trace'):
        with (tmp/(trace.stem+'.parsed')).open('w') as f:
            subprocess.run(['go','tool','trace','-d=parsed',trace],env=env,stdout=f,check=True)
