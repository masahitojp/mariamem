"""Owned-workspace runner; copy to evidence/run.py before invoking phases."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import selectors
import shutil
import subprocess
import sys

W=Path(__file__).resolve().parents[1]
C,T,E=W/'worktree',W/'temp',W/'evidence'
S=C/'benchmarks/forkattribution'
sys.path.insert(0,str(C/'scripts'))
from git_identity import ReleasePin,require_commit,verify_release_pin


def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2)+'\n')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['build','pilot','measure'],required=True);phase=p.parse_args().phase
    plan=json.loads((S/'plan.json').read_text());pin=plan['sources']['mariamem'];product=T/'product'
    verify_release_pin(product,ReleasePin(**pin));require_commit(product,pin['source_commit'])
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=product,text=True).strip()==pin['source_commit']
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=product,text=True)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip();require_commit(C,commit)
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=C,text=True)
    env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_','GODEBUG','GOMEMLIMIT','GOGC','GOFLAGS'))}
    env.update(GOTOOLCHAIN='local',CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(T/'go-cache'),GOMODCACHE=str(T/'go-mod'),GOTMPDIR=str(T/'go-tmp'),TMPDIR=str(T/'scratch'))
    for leaf in ['go-cache','go-mod','go-tmp','scratch','bin']:(T/leaf).mkdir(exist_ok=True)
    go=shutil.which('go');assert subprocess.check_output([go,'version'],env=env,text=True).strip()=='go version go1.27.3 darwin/arm64'
    if phase=='build':
        overlays={str(product/'internal/generatedgo'/name):str(S/'overlay'/(name+'.txt')) for name in ['attribution.go','memory_backing_unix.go']}
        save(T/'overlay.json',dict(Replace=overlays))
        data=dict(plan=plan,harness_source_commit=commit,host=dict(os=platform.mac_ver()[0],arch=platform.machine(),cpu='Apple M1',ram_bytes=17179869184),binaries={},source_sha256={str(f.relative_to(S)):digest(f) for f in S.rglob('*') if f.is_file()},overlay={name:dict(original_sha256=digest(Path(name)) if Path(name).exists() else None,overlay_sha256=digest(Path(value))) for name,value in overlays.items()})
        for label in ['profile','stages']:
            cmd=[go,'build','-mod=readonly','-p','1','-trimpath','-buildvcs=true','-o',str(T/'bin'/label)]
            if label=='stages':cmd+=['-overlay',str(T/'overlay.json')]
            cmd+=['./'+label]
            print('BUILD',label,flush=True)
            with (E/('build-'+label+'.txt')).open('w') as f:subprocess.run(cmd,cwd=S,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=1200)
            info=subprocess.check_output([go,'version','-m',T/'bin'/label],env=env,text=True)
            assert 'vcs.revision='+commit in info and 'vcs.modified=false' in info
            data['binaries'][label]=dict(sha256=digest(T/'bin'/label),build_info=info,overlay_applied=label=='stages')
        save(E/'inputs.json',data);print('BUILD PASS',flush=True);return
    inputs=json.loads((E/'inputs.json').read_text());assert inputs['harness_source_commit']==commit
    for label,d in inputs['binaries'].items():assert digest(T/'bin'/label)==d['sha256']
    records=[]
    def run(label,rep,negative=False,count=100):
        name=f'{phase}/{label}-{rep}'+('-negative' if negative else '')
        out=E/(name+'.json');out.parent.mkdir(parents=True,exist_ok=True)
        scratch=T/'scratch'/name;scratch.mkdir(parents=True)
        cmd=[str(T/'bin'/label),'-out',str(out)]
        if negative:cmd+=['-corrupt']
        if label=='profile':cmd+=['-profile',str(E/(name+'.pprof')),'-count',str(count)]
        rss=[]
        with (E/(name+'.stderr.txt')).open('w') as log:
            if label=='profile':
                code=subprocess.run(cmd,cwd=C,env=dict(env,TMPDIR=str(scratch)),stdout=log,stderr=subprocess.STDOUT,timeout=100).returncode
            else:
                proc=subprocess.Popen(cmd,cwd=C,env=dict(env,TMPDIR=str(scratch)),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,text=True,bufsize=1)
                sel=selectors.DefaultSelector();sel.register(proc.stdout,selectors.EVENT_READ)
                try:
                    while True:
                        assert sel.select(timeout=30),'stage timeout'
                        line=proc.stdout.readline()
                        if not line:break
                        event=json.loads(line);observed=int(subprocess.check_output(['/bin/ps','-o','rss=','-p',str(proc.pid)],text=True).strip())*1024
                        rss.append(dict(stage=event['stage'],rss_bytes=observed));save(E/(name+'.rss.json'),rss)
                        proc.stdin.write('continue\n');proc.stdin.flush()
                    code=proc.wait(timeout=10)
                finally:
                    sel.close()
                    if proc.poll() is None:proc.kill();proc.wait()
                    proc.stdin.close();proc.stdout.close()
        d=json.loads(out.read_text());assert not any(scratch.iterdir())
        if negative:assert code!=0 and not d['success'] and 'pristine oracle' in d['error']
        else:
            assert code==0 and d['success']
            if label=='profile':assert d['count']==count
            else:
                assert d['cleanup_complete'] and len(d['events'])==11
                assert d['events'][-1]['mapping']['active_mappings']==0
                assert all(x['mapping']['grow_calls']==x['mapping']['creates'] for x in d['events']), 'guest grew beyond observed span'
                assert [x['stage'] for x in rss]==[x['stage'] for x in d['events']]
        row=dict(name=name,negative=negative,report=name+'.json',rss=name+'.rss.json' if label=='stages' else None,profile=name+'.pprof' if label=='profile' else None,returncode=code,scratch_empty=True)
        records.append(row);save(E/(phase+'-records.json'),records);print('PASS',name,flush=True)
    if phase=='pilot':
        run('profile',0,count=2);run('profile',0,negative=True,count=1);run('stages',0);run('stages',0,negative=True)
        save(E/'pilot-result.json',dict(result='PASS',positive=2,negative=2))
    else:
        assert json.loads((E/'pilot-result.json').read_text())['result']=='PASS'
        for rep in range(2):run('profile',rep)
        for rep in range(5):run('stages',rep)
        for rep in range(2):
            for mode,flags in [('flat',[]),('cum',['-cum'])]:
                out=E/f'measure/profile-{rep}-{mode}.txt'
                with out.open('w') as f:subprocess.run([go,'tool','pprof','-top','-nodecount=60','-unit=ms',*flags,str(T/'bin/profile'),str(E/f'measure/profile-{rep}.pprof')],env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=30)
        save(E/'completion.json',dict(result='PASS',profile_processes=2,profile_children=200,stage_processes=5,retained_children=10,scope='Attribution only: no sharing algorithm/product change; staged runs are intrusive and not latency evidence'))

if __name__=='__main__':main()
