#!/usr/bin/env python3
"""Small fixed-input experiment; no production modification or full guest run."""
import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time

SOURCE = '47f297cc7498625e076abb93322eb616c9560bb8'
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def u(n):
    result=[]
    while n>=128:
        result.append((n&127)|128);n>>=7
    return bytes(result+[n])

def signed(n):
    result=[]
    while True:
        b=n&127;n>>=7
        stop=(n==0 and not b&64) or (n==-1 and b&64)
        result.append(b if stop else b|128)
        if stop:return bytes(result)

def vec(xs):return u(len(xs))+b''.join(xs)
def sec(k,b):return bytes([k])+u(len(b))+b
def typ(ps,rs):return b'\x60'+vec([bytes([x]) for x in ps])+vec([bytes([x]) for x in rs])
def const(n):return b'\x41'+signed(n)
def local(n):return b'\x20'+u(n)
def simd(op,align=3,offset=0):return b'\xfd'+u(op)+u(align)+u(offset)

def wasm():
    # Memory globals and copy expression match the selected generated helper.
    copy=(const(24020976)+local(0)+simd(0)+simd(11)+
          const(24020896)+const(24020768)+simd(0)+simd(11))
    # One v128 read, then extract its two i64 lanes from a local value.
    read=(const(24020976)+simd(0)+b'\x21\x00'+
          local(0)+b'\xfd\x1d\x00'+local(0)+b'\xfd\x1d\x01')
    rdv=const(24020776)+b'\x29\x03\x00'
    wrv=const(24020776)+local(0)+b'\x37\x03\x00'
    lock=(b'\x03\x40'+local(0)+const(0)+const(1)+b'\xfe\x48\x02\x00'+b'\x0d\x00\x0b')
    unlock=local(0)+const(0)+b'\xfe\x17\x02\x00'
    types=[typ([0x7f],[]),typ([],[0x7e,0x7e]),typ([],[0x7e]),typ([0x7e],[])]
    funcs=[(0,'copy_head',b'\x00',copy),(1,'read_head',b'\x01\x01\x7b',read),
           (2,'read_view',b'\x00',rdv),(3,'write_view',b'\x00',wrv),
           (0,'lock',b'\x00',lock),(0,'unlock',b'\x00',unlock)]
    imports=b'\x01\x03env\x06memory\x02\x03'+u(400)+u(400)
    exports=vec([u(len(name))+name.encode()+b'\0'+u(i) for i,(_,name,_,_) in enumerate(funcs)])
    bodies=[prefix+code+b'\x0b' for _,_,prefix,code in funcs]
    return b'\0asm\x01\0\0\0'+sec(1,vec(types))+sec(2,imports)+sec(3,vec([u(t) for t,_,_,_ in funcs]))+sec(7,exports)+sec(10,vec([u(len(b))+b for b in bodies]))

def finite_model():
    # Enumerate a single monotonic publication A→B, not the alternating stress.
    rows=[]
    for schedule in itertools.permutations(('W0','W1','R0','R1')):
        if schedule.index('W0')>schedule.index('W1') or schedule.index('R0')>schedule.index('R1'):continue
        memory=[100,900];observed=[None,None]
        for event in schedule:
            lane=int(event[1])
            if event[0]=='W':memory[lane]=[101,0][lane]
            else:observed[lane]=memory[lane]
        rows.append({'schedule':schedule,'read':observed,'ahead_of_published':tuple(observed)>(101,0)})
    assert any(r['read']==[101,900] for r in rows)
    assert {tuple(r['read']) for r in rows}=={(100,900),(101,0),(100,0),(101,900)}
    def word_ok(v,a,b):
        return all(((v>>i)&255) in (((a>>i)&255),((b>>i)&255)) for i in range(0,64,8))
    # Independent validation of the driver's classifications, including negative
    # controls; a mixed published tuple is not itself a Wasm violation.
    for pair in ((100,900),(101,0),(100,0),(101,900)):
        assert word_ok(pair[0],100,101) and word_ok(pair[1],900,0)
    assert not word_ok(102,100,101)
    assert not word_ok(0x3333333333333333,0x1111111111111111,0x2222222222222222)
    return {'one_transition_schedules':rows,'coherence_negative_control':[101,900],
            'byte_oracle_negative_controls':[102,'0x3333333333333333'],
            'result':'PASS: abstract schedules/oracle controls; not real SQL execution'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--temp',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True)
    p.add_argument('--iterations',type=int,default=300000);p.add_argument('--repeats',type=int,default=3)
    a=p.parse_args();temp=a.temp.resolve();out=a.evidence.resolve();temp.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True,exist_ok=True)
    start=time.time()
    def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args])
    # SHA is resolved by the shared identity tool, not inferred from its shape.
    identity=json.loads(subprocess.check_output(['python3',str(ROOT/'scripts/git_identity.py'),'inspect',SOURCE]))
    assert identity['source_commit']==SOURCE
    inventory={}
    for name in git('ls-tree','-r','--name-only',SOURCE,'internal/generatedgo/code/base').decode().splitlines():
        raw=git('show',SOURCE+':'+name)
        assert (ROOT/name).read_bytes()==raw, 'unapproved current base differs: '+name
        inventory[name]=digest(raw)
    template_hashes={f.name:digest(f.read_bytes()) for f in HERE.iterdir() if f.is_file()}
    env={**os.environ,'GOTOOLCHAIN':'go1.26.8','GOWORK':'off','GOENV':'off','GOFLAGS':'','GOEXPERIMENT':'',
         'GOCACHE':str(temp/'gocache')}
    path=temp/'fixture.wasm';path.write_bytes(wasm())
    (out/'fixture.wasm').write_bytes(path.read_bytes())
    probe=ROOT/'build/purge-probe.go';probe.parent.mkdir(exist_ok=True);shutil.copyfile(HERE/'probe.go.txt',probe)
    commands=[]
    def command(argv,timeout=180,extra_env=None):
        t=time.time();r=subprocess.run(list(map(str,argv)),cwd=ROOT,env={**env,**(extra_env or {})},capture_output=True,text=True,timeout=timeout)
        commands.append({'argv':[str(x).replace(str(temp),'<temp>').replace(str(ROOT),'<repo>') for x in argv],
                         'exit_code':r.returncode,'seconds':time.time()-t})
        return r
    for race in (False,True):
        binary=temp/('probe-race' if race else 'probe')
        r=command(['go','build','-mod=readonly','-trimpath','-buildvcs=false',*(['-race'] if race else []),'-o',binary,probe])
        (out/('build-race.txt' if race else 'build.txt')).write_text(r.stdout+r.stderr)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)
    rows=[]
    oracle_rows=[]
    for argv in ([temp/'probe','oracle'],['node',HERE/'reference.cjs','oracle']):
        r=command(argv);assert r.returncode==0,r.stdout+r.stderr
        check=json.loads(r.stdout);assert check['result']=='PASS' and check['oracle_controls']==12
        oracle_rows.append(check)
    for trial in range(a.repeats):
        for kind in ('head','view'):
            for mode in ('distinct','shared','ordered'):
                n=min(a.iterations,10000) if mode=='ordered' else a.iterations
                drivers=[('Wasm',['node',HERE/'reference.cjs',path,kind,mode,n],None)]
                drivers.extend(('Go',[temp/'probe',kind,mode,backing,n],backing) for backing in ('heap','mmap'))
                for label,argv,backing in drivers:
                    r=command(argv);assert r.returncode==0,r.stdout+r.stderr
                    row=json.loads(r.stdout);assert row['counts']['reads']==n and row['counts']['forbidden']==0
                    rows.append({**row,'trial':trial,'race':False})
                    print(label,kind,mode,backing,'trial',trial,'hybrid',row['counts']['hybrid'],flush=True)
    # Diagnostic only: halt at FIRST report; no broad census/count inference.
    for kind in ('head','view'):
        for mode in ('distinct','shared'):
            for backing in ('heap','mmap'):
                r=command([temp/'probe-race',kind,mode,backing,10000],extra_env={'GORACE':'halt_on_error=1 exitcode=66'})
                name=f'race-{kind}-{mode}-{backing}.txt'
                log=(r.stdout+r.stderr).replace(str(ROOT),'<repo>').replace(str(temp),'<temp>')
                (out/name).write_text(log)
                assert r.returncode in (0,66),log
                if mode=='shared':assert r.returncode==0,log
                rows.append({'engine':'Go','kind':kind,'mode':mode,'backing':backing,'race':True,
                             'iterations':10000,'exit_code':r.returncode,'reports_before_halt':log.count('WARNING: DATA RACE'),
                             'counts':json.loads(r.stdout)['counts'] if r.returncode==0 else None,'log':name,
                             'log_sha256':digest(log.encode())})
    r=command(['go','tool','objdump','-s','base.Simd_v128_(load|store)$',temp/'probe'])
    assert r.returncode==0
    (out/'go-disassembly.txt').write_text(r.stdout.replace(str(ROOT),'<repo>'))
    model=finite_model();(out/'model.json').write_text(json.dumps(model,indent=2)+'\n')
    result={'source_identity':identity,'experiment_base_commit':git('rev-parse','HEAD').decode().strip(),
            'base_inventory_sha256':inventory,'fixture_sha256':digest(path.read_bytes()),'template_sha256':template_hashes,
            'node_version':subprocess.check_output(['node','--version'],text=True).strip(),
            'go_version':subprocess.check_output(['go','version'],env=env,text=True).strip(),
            'platform':platform.platform(),'machine':platform.machine(),'duration_seconds':time.time()-start,
            'iterations':a.iterations,'repeats':a.repeats,'oracle_controls':oracle_rows,'runs':rows,'commands':commands,
            'limits':['not a translated complete guest','abstracted CAS mutexes, not production srw slow paths',
                      'alternating stress is not a MariaDB workload','no SQL harm test','no complete memory-model proof',
                      'mmap zero reports does not imply safety','Ubuntu not executed']}
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Saved',out/'results.json',flush=True)

if __name__=='__main__':main()
