#!/usr/bin/env python3
"""Runtime-only exact-source qualification; no artifacts, comparison or publication.

This replaces the v0.4.4 combined Product runner. Historical receipts cannot
satisfy runtime-qualification-v1. Measurement remains a separate manual task.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from consumer_acceptance import environment
from git_identity import require_commit
from experiment_workspace import remove_disposable_tree
from runtime_validation import CONTRACT, BOUNDARIES, WORKFLOW, tree, source_inventory

ROOT = Path(__file__).resolve().parents[1]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def qualify(root, candidate, workspace, native_platform):
    require_commit(root, candidate)
    if subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip() != candidate:
        raise ValueError('source must be exact candidate')
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True).strip():
        raise ValueError('source must be clean')
    if workspace == root or workspace.is_relative_to(root):
        raise ValueError('workspace must be outside disposable source checkout')
    env_info = environment(native_platform)
    if native_platform == 'darwin-arm64':
        valid = env_info['system'] == 'Darwin' and env_info['architecture'] == 'arm64' and env_info['product_version'].startswith('15.')
    else:
        valid = env_info['system'] == 'Linux' and env_info['architecture'] == 'x86_64' and env_info['distribution'] == 'ubuntu' and env_info['version_id'] == '24.04'
    if not valid:
        raise ValueError('requires actual minimum supported native platform')
    if not sys.version.startswith('3.14.'):
        raise ValueError('requires Python3.14')
    evidence, scratch = workspace/'evidence', workspace/'scratch'
    if scratch.exists() or (evidence/'inputs.json').exists():
        raise ValueError('refuse stale qualification evidence/scratch')
    # Authenticate every tracked input and mode, not an installed-wheel subset.
    inventory = source_inventory(root, candidate)
    git_tree = tree(root, candidate)
    evidence.mkdir(parents=True, exist_ok=True)
    scratch.mkdir()
    # No ambient pytest selection or Go/runtime override may narrow the oracle.
    env = {k:v for k,v in os.environ.items() if k not in ('GH_TOKEN','GITHUB_TOKEN')
           and not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','WASMER_','WASIX_',
                                 'DYLD_','LD_','PYTEST','PYTHON'))}
    env.update(GOTOOLCHAIN='go1.26.8', GOMAXPROCS='2', GOENV='off', GOWORK='off',
               GOFLAGS='', GOEXPERIMENT='', CGO_ENABLED='1',
               GOCACHE=str(scratch/'gocache'), GOPATH=str(scratch/'gopath'),
               TMPDIR=str(scratch), GOTMPDIR=str(scratch), PIP_NO_CACHE_DIR='1',
               PYTHONDONTWRITEBYTECODE='1')
    inputs = {'version':1, 'contract':CONTRACT, 'result':'FAIL', 'candidate_sha':candidate,
              'native_platform':native_platform, 'environment':env_info, 'python':sys.version,
              'guest_sha256':json.loads((root/'release/generated-go-inputs.json').read_text())['guest_sha256'],
              'git_tree_sha256':hashlib.sha256(json.dumps(git_tree, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
              'harness_sha256':{n:inventory[n] for n in inventory if
                               n in (WORKFLOW, 'scripts/verify.py', 'scripts/validate_product_candidate.py') or
                               n.startswith(('tests/', 'scripts/vet_generated.py'))},
              'started_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    write(evidence/'source-inventory.json', inventory)
    inputs['source_inventory_sha256'] = sha256(evidence/'source-inventory.json')
    commands=[]
    write(evidence/'correctness.json', {'version':1, 'contract':CONTRACT, 'result':'NOT READY', 'candidate_sha':candidate})
    started=time.monotonic()
    try:
        inputs['go_version'] = subprocess.check_output(['go','version'],cwd=root,env=env,text=True).strip()
        write(evidence/'inputs.json', inputs)
        for name, command in (('source-unit-checks','check'), ('runtime-integration','integration')):
            argv=[sys.executable,'scripts/verify.py',command]
            record={'name':name,'argv':argv}; commands.append(record)
            write(evidence/'commands.json',commands)
            print('+',name,flush=True)
            begun=time.monotonic()
            with (evidence/(name+'.log')).open('w') as stream:
                result=subprocess.run(argv,cwd=root,env=env,stdout=stream,stderr=subprocess.STDOUT)
            record.update(exit_code=result.returncode,seconds=time.monotonic()-begun)
            write(evidence/'commands.json',commands)
            if result.returncode:
                raise RuntimeError(name+' failed; see its log')
        if inventory != source_inventory(root,candidate) or subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip():
            raise ValueError('source changed during qualification')
        inputs['result']='PASS'
        write(evidence/'correctness.json', {'version':1,'contract':CONTRACT,'result':'PASS',
                                         'candidate_sha':candidate,'boundaries':sorted(BOUNDARIES)})
    except Exception as error:
        inputs['error']=str(error)
        raise
    finally:
        inputs['total_seconds']=time.monotonic()-started
        write(evidence/'inputs.json',inputs)
        # This entry explicitly requires a disposable checkout. Build products
        # and test-owned synthetic repositories are recreatable, never receipts.
        remove_disposable_tree(scratch)
        for p in (root/'tests/runs', root/'tests/evidence'):
            remove_disposable_tree(p)
        if (root/'build').exists():
            for p in (root/'build').iterdir():
                if p.name != 'go.mod': remove_disposable_tree(p)
        write(evidence/'cleanup.json', {'scratch_removed':not scratch.exists()})
        write(evidence/'SHA256SUMS.json',{p.name:sha256(p) for p in sorted(evidence.iterdir())
                                         if p.is_file() and p.name!='SHA256SUMS.json'})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-sha',required=True)
    parser.add_argument('--platform',required=True,choices=('darwin-arm64','ubuntu24.04-x86_64'))
    parser.add_argument('--workspace',type=Path,required=True)
    parser.add_argument('--disposable-checkout',action='store_true',required=True)
    args=parser.parse_args()
    qualify(ROOT,args.candidate_sha,args.workspace.resolve(),args.platform)


if __name__=='__main__': main()
