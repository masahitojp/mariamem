#!/usr/bin/env python3
"""Bounded source-contact probe, not a registered/prepared/build-qualified engine.

Reproduce with an exact upstream Git checkout/object database and fresh output.
Loads reviewed13.0.2 input bytes but NEVER calls them13.2 acceptance. Records
fuzz0 patch application without repinning old input expectations.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'scripts'))
from common import digest, extract, fetch
from git_identity import require_commit
from guest_preparation_context import resolve, read_input

SOURCE = 'c9f28ba0afec6d29e4688255dce8caaf7e91233d'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--downloads', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    identity = require_commit(args.upstream, SOURCE)
    source = args.output.resolve()
    source.mkdir(parents=True, exist_ok=False)
    args.evidence.mkdir(parents=True, exist_ok=True)
    resolved = resolve(ROOT, '13.0.2', 'native-text')
    guest = resolved['guest_input']
    groups = [*guest['patches'], guest['source_overlay'], guest['observation_overlay'], guest['native_overlay']]
    names = {'VERSION', '.gitmodules', 'scripts/mariadb_system_tables.sql',
             'mysql-test/std_data/unicode/allkeys1400.txt'}
    for patch in groups:
        names.update(patch['before_sha256'])
    names.update(resolved['effective_lock']['pristine_files'])
    members = set(subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', SOURCE], cwd=args.upstream,text=True).splitlines())
    for name in sorted(names & members):
        path = source/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(subprocess.check_output(['git','show',SOURCE+':'+name],cwd=args.upstream))
    recipe_dir = source/'recipe-unpack'
    extract(fetch('lite4mariadb', lock=resolved['effective_lock'], downloads=args.downloads), recipe_dir)
    recipe = next(recipe_dir.iterdir())
    for name, expected in guest['recipe_files_sha256'].items():
        if digest(recipe/name) != expected:raise ValueError('recipe mismatch: '+name)
        (source/name).parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(recipe/name,source/name)
    shutil.rmtree(recipe_dir)
    observed = []
    report = {'scope':'fuzz0 source-contact probe; no input registration, build, or runtime acceptance',
              'source_commit':identity.source_commit,'tag_object_sha':None,
              'upstream_ref':'refs/heads/preview-13.2-preview','version_text':(source/'VERSION').read_text(),
              'baseline_selection':resolved['selection'],'baseline_resolved_sha256':resolved['resolved_sha256'],
              'patches':observed}
    for number, patch in enumerate(groups):
        path = args.evidence/f'input-{number}.patch'
        path.write_bytes(read_input(ROOT,resolved['files'][patch['file']]['file']))
        before = {name:digest(source/name) if (source/name).is_file() else None for name in patch['before_sha256']}
        result = subprocess.run(['patch','--batch','--forward','--fuzz=0','-p1','-i',str(path.resolve())],cwd=source,text=True,capture_output=True)
        log=result.stdout+result.stderr
        (args.evidence/f'patch-{number}.txt').write_text(log)
        after = {name:digest(source/name) if (source/name).is_file() else None for name in patch['after_sha256']}
        observed.append({'file':patch['file'],'patch_sha256':digest(path),'before_sha256':before,'after_sha256':after,
                         'changed_preimages':[name for name,h in before.items() if h!=patch['before_sha256'][name]],
                         'returncode':result.returncode,'log':f'patch-{number}.txt'})
        path.unlink() # Original bytes remain in the immutable registered inputs.
        (args.evidence/'probe.json').write_text(json.dumps(report,indent=2)+'\n')
        print(patch['file'], 'PASS' if result.returncode==0 else 'FAIL',flush=True)
        if result.returncode:
            for reject in source.rglob('*.rej'):
                target=args.evidence/(reject.relative_to(source).as_posix().replace('/','__')+'.txt')
                target.write_bytes(reject.read_bytes())
            return 1
    return 0


if __name__=='__main__':
    raise SystemExit(main())
