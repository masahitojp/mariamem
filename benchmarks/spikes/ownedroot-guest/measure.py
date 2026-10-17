#!/usr/bin/env python3
"""Alternate exact-source baseline/candidate workflows after correctness checks."""
import argparse,hashlib,json,os,subprocess,sys
from dataclasses import asdict
from pathlib import Path
from check import ROOT,GO,environment,modules,clean

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);a=p.parse_args();w=a.workspace.resolve();e=w/'evidence/measurement';e.mkdir(exist_ok=True)
    sys.path.insert(0,str(ROOT/'scripts'))
    from git_identity import inspect_ref,read_release_pin,verify_release_pin,require_commit,verify_go_binary
    pin=read_release_pin(ROOT/'release/baselines/v0.5.1.json');verify_release_pin(ROOT,pin)
    candidate=inspect_ref(ROOT,'HEAD').source_commit
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT).strip()
    env=environment(w);modules(env);sources={'baseline':pin.source_commit,'candidate':candidate};binaries={};receipt={'baseline':asdict(pin),'candidate_source_commit':candidate,'builds':{},'cells':[],'diagnostics':[]}
    def save():(e/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    observer=None
    for label,commit in sources.items():
        checkout=w/'temp'/('measure-'+label)
        subprocess.run(['git','clone','--quiet','--shared','--no-checkout',str(ROOT),str(checkout)],check=True)
        subprocess.run(['git','checkout','--quiet','--detach',commit],cwd=checkout,check=True);require_commit(checkout,commit)
        assert not subprocess.check_output(['git','status','--porcelain'],cwd=checkout).strip()
        src=checkout/'benchmarks/ownedprepared/main.go';text=src.read_text();modified=text.replace('\tb, e := json.MarshalIndent(result','\tresult["final_go"] = goResourcePoint()\n\tb, e := json.MarshalIndent(result')
        assert text!=modified
        if observer is None:observer=modified;(e/'observer-main.go.txt').write_text(modified)
        else:assert observer==modified,'Use exactly the same benchmark observer for both sources'
        overlay=w/'temp'/('observer-'+label+'.go');overlay.write_text(modified);mapping=w/'temp'/('overlay-'+label+'.json');mapping.write_text(json.dumps({'Replace':{str(src):str(overlay)}})+'\n')
        binary=w/'temp'/('measure-'+label+'-bin');cmd=[str(GO),'build','-p','1','-trimpath','-buildvcs=true','-overlay',str(mapping),'-o',str(binary),'./benchmarks/ownedprepared']
        log=subprocess.run(cmd,cwd=checkout,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=1200);(e/('build-'+label+'.txt')).write_text(clean(log.stdout,w));assert log.returncode==0,log.stdout[-2000:]
        stamp=verify_go_binary(checkout,binary,commit,go=GO)
        receipt['builds'][label]={'source_commit':commit,'binary_sha256':digest(binary),'build_info':clean(stamp,w),'observer_sha256':digest(overlay),'original_harness_sha256':digest(src)};binaries[label]=binary;save();print('BUILD PASS',label,flush=True)
    def run(label,payload,workers,trial,traced=False):
        name=f'{payload}MiB-w{workers}-{trial:02d}-{label}'+('-trace' if traced else '')
        out=e/(name+'.json');runenv=dict(env)
        if traced:
            td=e/name;td.mkdir();runenv['MARIAMEM_TIMING_DIR']=str(td)
        cmd=[str(binaries[label]),'-payload-mib',str(payload),'-tables','1','-workers',str(workers),'-forks','4','-workload','app-connections','-lifecycle','fork','-label',sources[label],'-out',str(out)]
        r=subprocess.run(cmd,env=runenv,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=90)
        (e/(name+'.txt')).write_text(clean(r.stdout,w));assert r.returncode==0,(name,r.stdout[-3000:])
        data=json.loads(out.read_text());mapping=data['final_go']['linear_memory_virtual'];assert mapping['creates']==mapping['releases']==5
        assert all(mapping[x]==0 for x in ('active_mappings','active_reserved_bytes','active_rw_bytes','release_failures'))
        cell={'name':name,'label':label,'payload_mib':payload,'workers':workers,'trial':trial,'result_sha256':digest(out),'product_seconds':data['suite_product_seconds']}
        receipt['diagnostics' if traced else 'cells'].append(cell);save();print('PASS',name,round(data['suite_product_seconds']*1000,2),flush=True)
    for payload,workers,repeats in [(0,1,10),(0,4,10),(10,1,3)]:
        for trial in range(repeats):
            for label in (['baseline','candidate'] if trial%2==0 else ['candidate','baseline']):run(label,payload,workers,trial)
    for workers in (1,4):
        for label in ('baseline','candidate'):run(label,0,workers,0,True)
    for label,commit in sources.items():
        assert digest(binaries[label])==receipt['builds'][label]['binary_sha256']
        assert not subprocess.check_output(['git','status','--porcelain'],cwd=w/'temp'/('measure-'+label)).strip()
    receipt['result']='PASS';save();print('PASS: 46 ordinary + 4 diagnostic workflows, no outlier removal',flush=True)
if __name__=='__main__':main()
