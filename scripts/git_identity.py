#!/usr/bin/env python3
"""Inspect source identity and verify pinned releases before expensive work."""
import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def _git(repository, *arguments):
    result = subprocess.run(['git', *arguments], cwd=repository, text=True, capture_output=True)
    if result.returncode:
        raise ValueError('Git identity check failed: ' + result.stderr.strip()[-1000:])
    return result.stdout.strip()


def _sha(value, field):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{40}', value):
        raise ValueError(f'{field} must be a full 40-character SHA')


@dataclass(frozen=True)
class GitIdentity:
    object_sha: str
    object_type: str
    source_commit: str


def inspect_ref(repository, ref):
    object_sha = _git(repository, 'rev-parse', '--verify', '--end-of-options', ref)
    _sha(object_sha, 'object_sha')
    kind = _git(repository, 'cat-file', '-t', object_sha)
    if kind not in ('commit', 'tag'):
        raise ValueError(f'expected source commit or tag; got {kind}')
    commit = _git(repository, 'rev-parse', object_sha + '^{commit}')
    return GitIdentity(object_sha, kind, commit)


def require_commit(repository, sha):
    """A 40-character hex string is insufficient: reject tag objects too."""
    _sha(sha, 'source_commit')
    identity = inspect_ref(repository, sha)
    if identity.object_type != 'commit':
        raise ValueError(f'expected commit SHA; got tag object {sha}; '
                         f'source_commit is {identity.source_commit}')
    return identity


@dataclass(frozen=True)
class ReleasePin:
    release_tag: str
    tag_object_sha: str
    source_commit: str

    def __post_init__(self):
        if not isinstance(self.release_tag, str) or not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.]+)?', self.release_tag):
            raise ValueError('release_tag must identify a versioned release')
        _sha(self.tag_object_sha, 'tag_object_sha')
        _sha(self.source_commit, 'source_commit')
        if self.tag_object_sha == self.source_commit:
            raise ValueError('tag_object_sha and source_commit must be distinct for an annotated release')


def read_release_pin(path):
    data = json.loads(Path(path).read_text())
    if (not isinstance(data, dict) or type(data.get('version')) is not int
            or data['version'] != 1
            or set(data) != {'version', 'release_tag', 'tag_object_sha', 'source_commit'}):
        raise ValueError('invalid release identity record')
    return ReleasePin(**{name: data[name] for name in ('release_tag', 'tag_object_sha', 'source_commit')})


def verify_release_pin(repository, pin, *, fetch_remote=None):
    if fetch_remote is not None:
        _git(repository, 'fetch', '--no-tags', '--', fetch_remote, pin.tag_object_sha)
    identity = inspect_ref(repository, pin.tag_object_sha)
    if identity.object_type != 'tag':
        raise ValueError('published baseline must be an annotated tag object')
    if identity.source_commit != pin.source_commit:
        raise ValueError('published baseline tag does not match the pinned release commit')
    # The immutable annotated object also records its release name.
    header = _git(repository, 'cat-file', '-p', pin.tag_object_sha).split('\n\n', 1)[0]
    if f'tag {pin.release_tag}' not in header.splitlines():
        raise ValueError('annotated tag name does not match release_tag')
    return identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    commands = parser.add_subparsers(dest='operation', required=True)
    inspect = commands.add_parser('inspect', help='read local commit/tag identity without fetching')
    inspect.add_argument('ref')
    verify = commands.add_parser('verify-release', help='validate both immutable release identities')
    verify.add_argument('--pin', type=Path, required=True)
    verify.add_argument('--fetch', metavar='REMOTE', help='explicitly fetch only the pinned tag object')
    verify.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        if args.operation == 'inspect':
            report = asdict(inspect_ref(args.root, args.ref))
        else:
            pin = read_release_pin(args.pin)
            identity = verify_release_pin(args.root, pin, fetch_remote=args.fetch)
            report = {**asdict(pin), 'object_type': identity.object_type}
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
    except (ValueError, OSError) as error:
        parser.exit(1, f'Git identity preflight stopped: {error}\n')


if __name__ == '__main__':
    main()
