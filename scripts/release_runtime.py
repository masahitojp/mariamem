#!/usr/bin/env python3
"""Validate the shared release wheel and stage its exact host; never build."""
import argparse
from pathlib import Path
import zipfile

from common import ROOT, digest
from generated_release import checkout, read, require, verify_wheel, version, wheel_name
from git_identity import require_commit, verify_go_binary
from native_target import current_target


def stage(root, commit):
    require_commit(root, commit)
    checkout(root, commit)
    target = current_target(root)['platform']
    expected = Path('build/dist') / wheel_name(version(root)['PYTHON_VERSION'], target)
    record = read(root/'tests/evidence/alpha-wheel.json')
    require(record.get('wheel') == expected.as_posix(), 'shared wheel path differs')
    require(sorted((root/'build/dist').glob('*.whl')) == [root/expected], 'ambiguous shared wheels')
    for path in (root/expected, root/'tests/evidence/alpha-wheel.json', root/'build/mariamem-host'):
        require(not any(p.is_symlink() for p in (path, *path.parents)), 'shared runtime symlink')
    wheel, record = verify_wheel(root, target, commit)
    host = root/'build/mariamem-host'
    with zipfile.ZipFile(wheel) as archive:
        members = [n for n in archive.namelist() if n.endswith('/mariamem/_native/mariamem-host')]
        require(len(members) == 1, 'shared wheel host missing/duplicated')
        content = archive.read(members[0])
    if host.exists():
        require(digest(host) == record['manifest']['sha256']['mariamem-host'], 'existing shared host differs')
    else:
        host.write_bytes(content)
    host.chmod(0o755)
    require(digest(host) == record['manifest']['sha256']['mariamem-host'], 'shared host hash differs')
    actual = verify_go_binary(root, host, commit)
    # The path on the first line differs between build and consuming runners.
    require(actual.splitlines()[1:] == record['host_buildinfo'].splitlines()[1:], 'shared host build info differs')
    return wheel, host


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--source-commit', required=True)
    args = parser.parse_args()
    wheel, host = stage(args.root.resolve(), args.source_commit)
    print('Verified shared release wheel:', wheel.name)
    print('Verified shared release host:', host)


if __name__ == '__main__':
    main()
