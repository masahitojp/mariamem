#!/usr/bin/env python3
"""Apply historical legacy/native patches to the same pinned 13.2 source.

Source-only comparison: no registered legacy13.2 profile, build or runtime claim.
Archive hashes and original patch hashes are checked; changed old image hashes
are observations, never silently rebound product expectations.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
from common import digest, fetch
from guest_preparation_context import resolve, read_input


def select(archive, names, destination):
    seen = set()
    with tarfile.open(archive) as source:
        for member in source:
            name = member.name.partition('/')[2]
            if name not in names:
                continue
            if not member.isfile() or name in seen:
                raise ValueError('non-regular/duplicate selected member: ' + name)
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.extractfile(member).read())
            seen.add(name)
    return seen


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scratch', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    args.scratch.mkdir(parents=True, exist_ok=False)
    selected = resolve(ROOT, '13.2.0', 'native-text')
    downloads = args.scratch / 'downloads'
    source = fetch('mariadb', lock=selected['effective_lock'], downloads=downloads)
    recipe = fetch('lite4mariadb', lock=selected['effective_lock'], downloads=downloads)
    report = {'scope': 'same-upstream-diff patch application only',
              'source_commit': selected['guest_input']['source_commit'],
              'source_archive_sha256': digest(source), 'profiles': {}}
    for profile in ['legacy-full', 'native-text']:
        old = resolve(ROOT, '13.0.2', profile)
        guest = old['guest_input']
        stages = [*guest['patches'], guest['source_overlay'], guest['observation_overlay']]
        if 'native_overlay' in guest:
            stages.append(guest['native_overlay'])
        names = {n for stage in stages for n in stage['before_sha256']}
        work = args.scratch / profile
        work.mkdir()
        select(source, names, work)
        select(recipe, set(guest['recipe_files_sha256']), work)
        for name, expected in guest['recipe_files_sha256'].items():
            if digest(work / name) != expected:
                raise ValueError('recipe mismatch: ' + name)
        rows = []
        for i, stage in enumerate(stages):
            data = read_input(ROOT, old['files'][stage['file']]['file'])
            patch = args.scratch / ('%s-%d.patch' % (profile, i))
            patch.write_bytes(data)
            if digest(patch) != stage['sha256']:
                raise ValueError('patch changed')
            before = {name: digest(work/name) if (work/name).is_file() else None
                      for name in stage['before_sha256']}
            proc = subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1',
                                   '-i', str(patch.resolve())], cwd=work,
                                  text=True, capture_output=True)
            rows.append({'file': stage['file'], 'sha256': digest(patch),
                         'changed_preimages': sorted(n for n, h in before.items()
                                                     if h != stage['before_sha256'][n]),
                         'before_sha256': before,
                         'after_sha256': {n: digest(work/n) if (work/n).is_file() else None
                                          for n in stage['after_sha256']},
                         'returncode': proc.returncode, 'log': proc.stdout + proc.stderr})
            print(profile, i, proc.returncode, flush=True)
            if proc.returncode:
                break
        report['profiles'][profile] = rows
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    return int(any(r['returncode'] for rows in report['profiles'].values() for r in rows))


if __name__ == '__main__':
    raise SystemExit(main())
