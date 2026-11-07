#!/usr/bin/env python3
"""Rebind unchanged public lifecycle consumers to the C2 artifact, not all C3 faults."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',type=Path,required=True)
    w=parser.parse_args().workspace.resolve()
    sys.path.insert(0,str(ROOT/'scripts'))
    from dev_guest import inventory,source_identity
    origin=source_identity(ROOT)
    out=w/'temp/public';product=out/'product'
    source=json.loads((w/'evidence/public-source.json').read_text())
    assert source['source_inventory']==inventory(product)
    env=dict(os.environ,GOCACHE=str(w/'temp/gocache'),GOMODCACHE=str(w/'temp/gomodcache'),
             GOTOOLCHAIN='go1.26.10',CGO_ENABLED='0',GOMAXPROCS='2',GOWORK='off',GOFLAGS='')
    def run(argv,name,cwd):
        result=subprocess.run([str(v) for v in argv],cwd=cwd,env=env,text=True,
                              stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
        (w/'evidence'/(name+'.txt')).write_text(result.stdout)
        assert result.returncode==0,result.stdout
        return result.stdout
    binary=out/'live-consumer'
    run(['go','build','-p','1','-trimpath','-buildvcs=false','-o',binary,'./tests/live_acceptance/go_consumer'],
        'public-go-lifecycle-build',product)
    go=json.loads(run([binary,'-source-smoke'],'public-go-lifecycle',product).strip())
    assert go['result']=='PASS_SOURCE_GO_LIVE'
    python_fixture=ROOT/'tests/live_acceptance/installed_python.py'
    python=json.loads(run([w/'temp/venv/bin/python','-I',python_fixture],
                          'public-python-lifecycle',out/'consumer').strip())
    assert python['result']=='PASS_INSTALLED_PYTHON_LIVE'
    assert Path(python['module']).is_relative_to(w/'temp/venv')
    assert inventory(product)==source['source_inventory'] and source_identity(ROOT)==origin
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    # Preserve relative/semantic evidence, not the machine's install location.
    python.pop('module')
    (w/'evidence/public-lifecycle-result.json').write_text(json.dumps(dict(
        result='PASS bounded public lifecycle consumers',platform=sys.platform,
        host_source_commit=source['host_source_commit'],observer_source_commit=origin['commit'],
        source_receipt_sha256=sha(w/'evidence/public-source.json'),go_binary_sha256=sha(binary),
        go_fixture_sha256=sha(product/'tests/live_acceptance/go_consumer/main.go'),
        python_fixture_sha256=sha(python_fixture),go=go,python=python,
        not_verified=['full native C3 failure and permanent-debt injection','exact inherited durations and Live Reset settings',
                      'all original G1/G2/lifecycle oracles on this core','opposite native OS','performance','adoption','release']),indent=2)+'\n')


if __name__=='__main__':main()
