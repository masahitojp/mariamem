"""Bounded macOS Light Fork timing: ten alternating trace-off/on pairs."""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--go-root',type=Path,required=True)
    a=p.parse_args();w=a.workspace.resolve();root=Path(__file__).resolve().parents[2]
    sys.path.insert(0,str(root/'scripts'))
    from git_identity import require_commit,read_release_pin,verify_release_pin,verify_go_binary
    from experiment_disk import DiskGuard,run_guarded
    pin=read_release_pin(root/'release/baselines/v0.5.1.json');verify_release_pin(root,pin)
    checkout=w/'temp/source';subprocess.run(['git','clone','--quiet','--no-hardlinks','--no-checkout',str(root),str(checkout)],check=True)
    subprocess.run(['git','checkout','--quiet','--detach',pin.source_commit],cwd=checkout,check=True)
    identity=require_commit(checkout,pin.source_commit)
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=checkout)
    env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_')) and k not in ['GOGC','GOMEMLIMIT','GOMAXPROCS']}
    env.update(GOTOOLCHAIN='local',CGO_ENABLED='0',PATH=str(a.go_root/'bin')+os.pathsep+env['PATH'])
    for k,n in [('GOCACHE','go-cache'),('GOMODCACHE','go-mod'),('GOPATH','go-path'),('GOTMPDIR','go-tmp')]:
        env[k]=str(w/'temp'/n);Path(env[k]).mkdir(exist_ok=True)
    go=a.go_root/'bin/go';assert subprocess.check_output([go,'version'],env=env,text=True).strip()=='go version go1.26.8 darwin/arm64'
    replacements={};overlays=[]
    def overlay(rel,transform):
        source=checkout/rel;before=source.read_text();after=transform(before);assert before!=after
        out=w/'temp'/('overlay-'+str(len(overlays))+'.go');out.write_text(after);replacements[str(source)]=str(out)
        (w/'evidence'/('overlay-'+str(len(overlays))+'.go.txt')).write_text(after)
        overlays.append(dict(source=rel,source_sha256=sha(source),observer_sha256=sha(out)))
    def host(s):
        s=s.replace('func (s *Server) finish(ctx context.Context, export bool) error {','func (s *Server) finish(ctx context.Context, export bool) error {\n ctx, finishTiming := timing.Begin(ctx,"finish_breakdown"); defer finishTiming()')
        s=s.replace('\tcase <-done:\n\t\tif export {','\tcase <-done:\n\t\ttiming.Mark(ctx,"session_workers_drained")\n\t\tif export {')
        s=s.replace('\t\t\terr = s.Guest.Shutdown(ctx)','\t\t\ttiming.Mark(ctx,"shutdown_call_begin")\n\t\t\terr = s.Guest.Shutdown(ctx)\n\t\t\ttiming.Mark(ctx,"shutdown_call_returned")')
        return s
    overlay('internal/host/server.go',host)
    def capture(s):
        s=s.replace('\ts.Guest.RequestCapture()','\ttiming.Mark(ctx,"preconditions_checked")\n\ts.Guest.RequestCapture()')
        s=s.replace('\tif e := s.finish(ctx, false);','\ttiming.Mark(ctx,"before_finish")\n\tif e := s.finish(ctx, false);')
        s=s.replace('\timage := s.Guest.TakeCapture()','\ttiming.Mark(ctx,"finish_returned")\n\timage := s.Guest.TakeCapture()')
        s=s.replace('\towned, e := snapshot.OwnHeap','\ttiming.Mark(ctx,"before_own")\n\towned, e := snapshot.OwnHeap')
        s=s.replace('\treturn owned, true, e','\ttiming.Mark(ctx,"own_returned")\n\treturn owned, true, e')
        return s
    overlay('internal/host/heap_snapshot.go',capture)
    overlay('benchmarks/ownedprepared/main.go',lambda s:s.replace('\tb, e := json.MarshalIndent(result','\tresult["final_go"] = goResourcePoint()\n\tb, e := json.MarshalIndent(result'))
    overlaymap=w/'temp/overlay.json';overlaymap.write_text(json.dumps({'Replace':replacements})+'\n')
    binary=w/'temp/light-fork';guard=DiskGuard(w,20,8)
    build=[str(go),'build','-p','1','-trimpath','-buildvcs=true','-overlay',str(overlaymap),'-o',str(binary),'./benchmarks/ownedprepared']
    print('BUILD',flush=True);subprocess.run(build,cwd=checkout,env=env,check=True,timeout=900)
    receipt=dict(completed=False,source_identity=asdict(identity),tag_object_sha=pin.tag_object_sha,go='go1.26.8',host=subprocess.check_output(['uname','-a'],text=True).strip(),binary_sha256=sha(binary),binary_build_info=verify_go_binary(checkout,binary,pin.source_commit,go=go),overlays=overlays,runner_sha256=sha(Path(__file__)),cells=[],started=time.time())
    def save():(w/'evidence/receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    save()
    for trial in range(10):
        for traced in ([False,True] if trial%2==0 else [True,False]):
            name=f'{trial:02d}-'+('traced' if traced else 'plain');out=w/'evidence'/(name+'.json');runenv=dict(env)
            if traced:
                td=w/'evidence'/name;td.mkdir();runenv['MARIAMEM_TIMING_DIR']=str(td)
            command=[str(binary),'-payload-mib','0','-tables','1','-workers','1','-forks','4','-workload','app-connections','-lifecycle','fork','-label',pin.source_commit,'-out',str(out)]
            with (w/'evidence'/(name+'.txt')).open('w') as log:code=run_guarded(command,guard,cwd=checkout,env=runenv,output=log,timeout=45,interval=1)
            assert code==0,(name,code)
            d=json.loads(out.read_text());m=d['final_go']['linear_memory_virtual'];assert m['creates']==m['releases']==5
            assert m['active_mappings']==m['active_reserved_bytes']==m['active_rw_bytes']==m['release_failures']==0
            if traced:
                traces=[json.loads(p.read_text()) for p in td.glob('*.json')]
                for op,count in [('snapshot_freeze',1),('snapshot_own',1),('snapshot_capture',1),('fork',4),('startup',5),('finish_breakdown',5)]:assert sum(t['operation']==op for t in traces)==count,(op,len(traces))
            receipt['cells'].append(dict(name=name,trial=trial,traced=traced,result_sha256=sha(out),product_seconds=d['suite_product_seconds'],cpu_seconds=d['suite_cpu_seconds']));save();print('PASS',name,round(d['suite_product_seconds']*1000,2),flush=True)
    assert sha(binary)==receipt['binary_sha256'] and not subprocess.check_output(['git','status','--porcelain'],cwd=checkout)
    receipt.update(completed=True,ended=time.time(),peak_owned_bytes=guard.peak,minimum_free_bytes=guard.minimum_free);save()
    print('PASS: 20 workloads, 100 DB lifecycles, unchanged SQL/cleanup oracles',flush=True)


if __name__=='__main__':main()
