#!/usr/bin/env python3
"""Bounded first public execution of an exact selected candidate on either OS.

This finite route gate is not the full #132 configuration/fault/oracle cohort.
It reuses the independently built guest; it never rebuilds MariaDB for host tests.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from common import ROOT, digest
from dev_guest import external_output, inventory, require, source_identity, write
from experiment_disk import run_guarded
from git_identity import require_commit
from selected_guest_ci import ProducerBudget


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-commit', required=True)
    p.add_argument('--producer-root', type=Path, required=True)
    p.add_argument('--handoff', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--budget-gib', type=float, default=8)
    p.add_argument('--min-free-gib', type=float, default=8)
    a=p.parse_args()
    require_commit(ROOT,a.source_commit)
    identity=source_identity(ROOT)
    require(identity['commit']==a.source_commit,'wrong public candidate source')
    out=external_output(ROOT,a.output);out.mkdir(parents=True)
    for name in ('tmp','go-cache','go-path'):(out/name).mkdir()
    env=dict(os.environ,GOTOOLCHAIN='go1.26.10',GOWORK='off',GOENV='off',GOFLAGS='',GOEXPERIMENT='',
             PYTHONDONTWRITEBYTECODE='1',CGO_ENABLED='0',GOMAXPROCS='2',GOGC='50',GOCACHE=str(out/'go-cache'),
             GOMODCACHE=str(out/'go-path/pkg/mod'),GOPATH=str(out/'go-path'),
             TMPDIR=str(out/'tmp'),GOTMPDIR=str(out/'tmp'))
    guard=ProducerBudget([out,a.producer_root,a.handoff],a.min_free_gib,a.budget_gib)
    report={'source_commit':a.source_commit,'result':'INCOMPLETE','release_eligible':False,
            'scope':'Initial public routes only; full #132 acceptance NOT_RUN',
            'phases':[],'budget_gib':a.budget_gib,'min_free_gib':a.min_free_gib}
    def phase(name,command,timeout=900,cwd=ROOT,overrides=None,refusal=None):
        before=time.monotonic()
        with (out/(name+'.txt')).open('w') as log:
            rc=run_guarded([str(c) for c in command],guard,timeout=timeout,cwd=cwd,
                           env=dict(env,**(overrides or {})),output=log)
        report['phases'].append({'phase':name,'seconds':time.monotonic()-before,'exit_code':rc})
        write(out/'public-result.json',report)
        if refusal is None:
            require(rc==0,'selected public phase failed: '+name)
        else:
            require(rc==1 and refusal in (out/(name+'.txt')).read_text(),
                    'factory-disable control did not detect the missing factory: '+name)
    try:
        phase('install',[sys.executable,ROOT/'scripts/install_selected_guest.py','--producer-root',a.producer_root,
              '--handoff',a.handoff,'--engine','13.2.0','--profile','native-text','--output',out/'install'])
        product=out/'install/product'
        receipt=json.loads((out/'install/public-source.json').read_text())
        require(receipt['source_inventory']==inventory(product),'mixed public candidate source')
        # Build/test from this product only. Pattern selects the retained public
        # TCP/Pipe, capacity, fatal-cause/isolation and default-timeout oracles.
        phase('public-go',['go','test','-p','1','-trimpath','-buildvcs=false','-count=1','-timeout','180s','-v','-run','^TestNativePublic','.'],cwd=product)
        phase('host-owner-units',['go','test','-p','1','-trimpath','-buildvcs=false','-count=1','-timeout','120s',
              './internal/host','./internal/control','./internal/nativewire'],cwd=product)
        host=out/'mariamem-host'
        phase('host-build',['go','build','-p','1','-trimpath','-buildvcs=false','-o',host,'./cmd/mariamem-host'],cwd=product)
        info=subprocess.check_output([str(host),'--snapshot-info'],env=env,text=True)
        require(json.loads(info)['wasm_sha256']==receipt['guest_sha256'],'compiled host used old guest')
        phase('public-python',[sys.executable,'-m','pytest','-q',ROOT/'tests/test_dev_guest_smoke.py'],cwd=out,
              overrides={'PYTHONPATH':str(product/'python'),'MARIAMEM_TEST_HOST':str(host)})
        # Deliberate negative product; only the factory differs, and both
        # language oracles must fail with this exact startup cause (not timeout).
        factory=product/'internal/host/factory.go'
        positive=factory.read_bytes()
        marker='selected native factory disabled control'
        try:
            factory.write_text('package host\nimport ("context";"io";"time";"errors";'
                '"github.com/masahitojp/mariamem/internal/snapshot")\n'
                'func Start(context.Context,*snapshot.Owned,time.Duration,io.Writer)(Service,error) {'
                'return nil,errors.New("'+marker+'") }\n')
            negative=inventory(product)
            require({n for n in negative if negative[n]!=receipt['source_inventory'].get(n)}==
                    {'internal/host/factory.go'},'unexpected negative product drift')
            report['factory_disable_inventory']=negative
            phase('factory-disabled-go',['go','test','-p','1','-trimpath','-buildvcs=false','-count=1','-timeout','60s',
                  '-run','^TestNativePublicGoRoutes$','.'],cwd=product,refusal=marker)
            disabled=out/'disabled-host'
            phase('factory-disabled-host-build',['go','build','-p','1','-trimpath','-buildvcs=false',
                  '-o',disabled,'./cmd/mariamem-host'],cwd=product)
            phase('factory-disabled-python',[sys.executable,'-m','pytest','-q',ROOT/'tests/test_dev_guest_smoke.py'],
                  cwd=out,overrides={'PYTHONPATH':str(product/'python'),'MARIAMEM_TEST_HOST':str(disabled)},refusal=marker)
        finally:
            factory.write_bytes(positive)
        require(receipt['source_inventory']==inventory(product) and source_identity(ROOT)==identity,
                'public source changed during execution')
        report.update(result='PASS',guest_sha256=receipt['guest_sha256'],binding_sha256=receipt['binding_sha256'],
                      producer_source_commit=receipt['producer_source_commit'],
                      source_receipt_sha256=digest(out/'install/public-source.json'),
                      host_sha256=digest(host),go_buildinfo=subprocess.check_output(
                          ['go','version','-m',str(host)],env=env,text=True),resources=guard.check())
    except BaseException as exc:
        report.update(result='FAIL',error=type(exc).__name__+': '+str(exc))
        raise
    finally:
        write(out/'public-result.json',report)


if __name__=='__main__':main()
