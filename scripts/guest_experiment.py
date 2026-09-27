"""Small, explicitly non-production guest patch boundary."""
import os
from pathlib import PurePosixPath
import subprocess


def patch_files(root):
    patch = root / 'guest/experimental.patch'
    if not patch.exists():
        return []
    branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=root, text=True).strip()
    if not branch and os.environ.get('GITHUB_SHA') == subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip():
        branch = os.environ.get('GITHUB_REF_NAME', '')
    if not branch.startswith('experiment/'):
        raise ValueError('guest/experimental.patch requires an experiment/ branch')
    files = []
    for line in patch.read_text().splitlines():
        if line.startswith('+++ b/'):
            name = line[6:].split('\t', 1)[0]
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('unsafe experimental patch path')
            files.append(name)
        elif line.startswith('+++ /dev/null'):
            raise ValueError('experimental file deletion is not supported')
    if not files:
        raise ValueError('experimental patch must contain modified/new b/ files')
    return files
