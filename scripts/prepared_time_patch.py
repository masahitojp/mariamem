"""Exact-input experimental TIME metadata repair; never canonical adoption."""
import json
from pathlib import Path
import re
import subprocess

from common import ROOT, digest


def inputs(root=ROOT):
    root = Path(root)
    pin = json.loads((root/'guest/prepared_time_patch.json').read_text())
    source = json.loads((root/'guest/input.json').read_text())
    patch = root/'guest/experimental.patch'
    if (pin['source_commit'] != source['source_commit'] or
            pin['file'] != 'sql/sql_prepare.cc' or patch.is_symlink() or
            digest(patch) != pin['patch_sha256'] or
            re.findall(r'^\+\+\+ b/(.+)$', patch.read_text(), re.M) != [pin['file']]):
        raise ValueError('experimental TIME patch inputs changed')
    return pin


def apply(source, root=ROOT):
    root, source = Path(root), Path(source)
    pin = inputs(root)
    target = source/pin['file']
    if target.is_symlink() or digest(target) != pin['before_sha256']:
        raise ValueError('experimental TIME patch preimage changed')
    subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i',
                    str((root/'guest/experimental.patch').resolve())], cwd=source, check=True)
    if digest(target) != pin['after_sha256']:
        raise ValueError('experimental TIME patch postimage changed')
    return pin


if __name__ == '__main__':
    inputs()
    print('PASS: exact experimental TIME patch inputs')
