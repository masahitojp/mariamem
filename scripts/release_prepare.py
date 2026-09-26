#!/usr/bin/env python3
"""Thin preflight and preparation handoff to existing Release CI; never publish locally."""
import argparse
import json
from pathlib import Path
import re
import runpy
import subprocess
import sys

from common import ROOT

REPOSITORY = 'masahitojp/mariamem'
WORKFLOW = 'release-candidate-ready.yml'
VERSION = r'v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)-(alpha|beta|rc)\.([1-9][0-9]*)'


def parse_version(value):
    match = re.fullmatch(VERSION, value)
    if not match:
        raise ValueError('provide an explicit project-supported tag: vX.Y.Z-{alpha|beta|rc}.N')
    return match.groups()


def run(args, root):
    result = subprocess.run(args, cwd=root, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f'{args[0]} failed: {(result.stdout + result.stderr).strip()[-2000:]}')
    return result.stdout.strip()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def preflight(root, version, prepared=False):
    parse_version(version)
    require(run(['git', 'branch', '--show-current'], root) == 'main', 'release requires main branch')
    remote = run(['git', 'remote', 'get-url', '--push', 'origin'], root)
    require(remote in {f'git@github.com:{REPOSITORY}.git', f'https://github.com/{REPOSITORY}.git'},
            'origin push URL is not the mariamem repository')
    require(not run(['git', 'diff', '--name-only', '--diff-filter=U'], root), 'unresolved conflicts')
    if not prepared:
        require(not run(['git', 'status', '--porcelain'], root), 'working tree is dirty; do not sweep unrelated changes')
    require(not run(['git', 'tag', '--list', version], root), 'requested tag already exists locally')
    require(not run(['git', 'ls-remote', '--tags', 'origin', f'refs/tags/{version}', f'refs/tags/{version}^{{}}'], root),
            'requested tag already exists remotely')
    # List includes drafts visible to this account; errors/auth failures must not look like absence.
    releases = json.loads(run(['gh', 'api', '--paginate', '--slurp', f'repos/{REPOSITORY}/releases?per_page=100'], root))
    require(not any(item.get('tag_name') == version for page in releases for item in page),
            'requested GitHub release already exists')
    run(['git', 'fetch', 'origin', 'main'], root)
    run(['git', 'merge-base', '--is-ancestor', 'origin/main', 'HEAD'], root)
    commits = run(['git', 'log', '--oneline', 'origin/main..HEAD'], root)
    return {'version': version, 'unpushed_history': commits}


def submit(root, version):
    parse_version(version)
    preflight(root, version, prepared=True)
    canonical = runpy.run_path(str(root / 'python/mariamem/_version.py'))
    require(canonical['GIT_TAG'] == version, 'canonical version does not match explicit human version')
    notes = f"release/NOTES-{canonical['STAGE']}.{canonical['SERIAL']}.md"
    allowed = {'python/mariamem/_version.py', 'README.md', 'docs/go.md', 'docs/python.md', 'docs/releasing.md', notes}
    # Include staged, unstaged, and untracked paths, including both sides of renames.
    paths = set()
    for args in (['git', 'diff', '--name-only', '--no-renames'],
                 ['git', 'diff', '--cached', '--name-only', '--no-renames'],
                 ['git', 'ls-files', '--others', '--exclude-standard']):
        paths.update(run(args, root).splitlines())
    require(paths and paths <= allowed, 'unexpected or empty preparation changes: ' + ', '.join(sorted(paths - allowed)))
    require((root / notes).is_file() and re.search(r'^#\s+.*' + re.escape(version) + r'(?:\s|$)',
            (root / notes).read_text(), re.MULTILINE), 'release notes must identify requested tag')
    run([sys.executable, 'scripts/verify.py', 'check'], root)
    run(['git', 'diff', '--check'], root)
    run(['git', 'diff', '--cached', '--check'], root)
    run(['git', 'add', '--', *sorted(paths)], root)
    run(['git', 'commit', '-m', f'release: prepare {version} for CI publication'], root)
    require(not run(['git', 'status', '--porcelain'], root), 'tree not clean after preparation commit')
    candidate = run(['git', 'rev-parse', 'HEAD'], root)
    require(re.fullmatch('[0-9a-f]{40}', candidate) is not None, 'candidate is not an exact SHA')
    run(['git', 'push', 'origin', 'main'], root)
    remote = run(['git', 'ls-remote', 'origin', 'refs/heads/main'], root).split()
    require(remote == [candidate, 'refs/heads/main'], 'remote main does not equal candidate; no dispatch')
    output = run(['gh', 'workflow', 'run', WORKFLOW, '--ref', 'main', '-f', f'candidate_ref={candidate}',
                  '-f', 'mode=full', '-f', 'operation=release'], root)
    # gh prints the run URL on supported current versions. Never poll/redispatch to obtain it.
    match = re.search(r'https://github\.com/masahitojp/mariamem/actions/runs/[0-9]+', output)
    return {'version': version, 'candidate': candidate,
            'workflow': match.group() if match else f'https://github.com/{REPOSITORY}/actions/workflows/{WORKFLOW}',
            'submission': 'submitted', 'ci_owns_execution': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['preflight', 'submit'])
    parser.add_argument('version')
    args = parser.parse_args()
    try:
        result = preflight(ROOT, args.version) if args.operation == 'preflight' else submit(ROOT, args.version)
        print(json.dumps(result, indent=2))
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, f'Release preparation stopped: {exc}\nNo automatic rollback or redispatch.\n')


if __name__ == '__main__':
    main()
