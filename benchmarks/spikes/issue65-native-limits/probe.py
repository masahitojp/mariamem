#!/usr/bin/env python3
"""Fixed-guest remaining protocol limits: observation, no guest policy repair."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PREVIOUS=HERE.parent/'issue65-compat-fixes/probe.py'
spec=importlib.util.spec_from_file_location('fix_probe',PREVIOUS)
fix=importlib.util.module_from_spec(spec);spec.loader.exec_module(fix)
spec=importlib.util.spec_from_file_location('limits_observations',HERE/'observations.py')
limits=importlib.util.module_from_spec(spec);spec.loader.exec_module(limits)
analyze,require_extension=limits.analyze,limits.require_extension


def runtime(w):
    # The entire previously passed endpoint/binding/lifecycle/compatibility route
    # runs first, with its strict immutable macOS reference guard unchanged.
    subprocess.run([sys.executable,str(PREVIOUS),'runtime','--workspace',str(w)],check=True)
    base=fix.base
    build=json.loads((w/'evidence/host-build.json').read_text())
    product=w/'temp/host/product'
    sys.path.insert(0,str(w/'worktree/scripts'))
    from dev_guest import inventory
    before=inventory(product)
    if before!=build['source_inventory']:
        raise ValueError('baseline staged source changed')
    fixture=HERE/'limits_test.go.txt';target=product/'cmd/issue65-wire/limits_test.go'
    if target.exists():raise ValueError('refuse pre-existing limits fixture')
    shutil.copy2(fixture,target)
    actual=inventory(product)
    compared=require_extension(actual,before,base.sha(fixture))
    binary=w/'temp/host/limits.test'
    # Preserve the accepted baseline binary and pass no inherited environment
    # through command arguments/logs. The child constructs its scoped Go env.
    base.command(w,'limits-build',[sys.executable,Path(__file__),'compile','--workspace',w],600)
    if inventory(product)!=actual:raise ValueError('source changed during compilation')
    pin=base.sha(binary)
    base.save(w/'evidence/limits-build.json',{'tooling_source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'guest_source_commit':fix.GUEST_SOURCE,'guest_sha256':fix.GUEST_SHA,
              'baseline_binary_sha256':build['binary_sha256'],'binary_sha256':pin,
              'go_buildinfo':subprocess.check_output(['go','version','-m',str(binary)],env=fix.go_env(w),text=True),
              'fixture_sha256':base.sha(fixture),'source_inventory':actual,
              'baseline_matched_files':compared-1,'added_files':[target.relative_to(product).as_posix()]})
    exit_code=0
    try:base.command(w,'limits-suite',[binary,'-test.v','-test.run=^TestLimits','-test.timeout=240s'],270)
    except subprocess.CalledProcessError as error:exit_code=error.returncode
    result=analyze((w/'evidence/limits-suite.txt').read_text(),exit_code)
    if base.sha(binary)!=pin:raise ValueError('limits binary changed')
    if inventory(product)!=actual:raise ValueError('source changed during execution')
    result.update({'guest_sha256':fix.GUEST_SHA,'guest_source_commit':fix.GUEST_SOURCE,
                   'tooling_source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                   'binary_sha256':pin,'baseline_checks':'22 lifecycle +7 groups/88 observations +2 controls +supporting checks PASS',
                   'not_qualified':['full protocol/client profile','all command-specific input/metadata/multi-result bounds','public integration','controller relocation','race freedom','performance','release']})
    base.save(w/'evidence/limits-result.json',result)
    if not result['ready']:raise ValueError(result['result'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage',choices=['build','downloads','runtime','compile','cleanup']);p.add_argument('--workspace',type=Path,required=True)
    a=p.parse_args();w=a.workspace.resolve()
    if not (w/'experiment.json').is_file():p.error('owned workspace required')
    if a.stage not in ('runtime','compile'):
        subprocess.run([sys.executable,str(PREVIOUS),a.stage,'--workspace',str(w)],check=True);return
    owner=Path(json.loads((w/'experiment.json').read_text())['repo'])
    fix.base.safe_git(ROOT,w/'worktree',owner)
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    fix.base.identity(ROOT,sha);fix.base.identity(w/'worktree',fix.HOST_SOURCE)
    if a.stage=='compile':
        import platform
        if platform.system()!='Linux' or platform.machine()!='x86_64':raise ValueError('native Linux x86_64 compiler required')
        subprocess.run(['go','test','-c','-p','1','-trimpath','-buildvcs=false','-o',str(w/'temp/host/limits.test'),'./cmd/issue65-wire'],cwd=w/'temp/host/product',env=fix.go_env(w),check=True)
        return
    fix.base.save(w/'evidence/limits-tooling.json',{'tooling_source_commit':sha,'probe_sha256':fix.base.sha(Path(__file__)),'fixture_sha256':fix.base.sha(HERE/'limits_test.go.txt')})
    try:runtime(w)
    except Exception as error:
        fix.base.save(w/'evidence/limits-failure.json',{'error':str(error),'tooling_source_commit':sha});raise

if __name__=='__main__':main()
