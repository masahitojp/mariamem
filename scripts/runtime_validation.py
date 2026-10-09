#!/usr/bin/env python3
"""Authenticate Product CI runtime evidence separately from final release artifacts."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import zipfile

from common import ROOT, digest
from check_public import public_files, REPOSITORY_ONLY_FILES
from ci_release_reuse import GitHub, safe_name
from git_identity import require_commit

INTENT = 'release/runtime-validation.json'
PROOF = 'build/release/runtime-validation.json'
WORKFLOW = '.github/workflows/v044-product-validation.yml'
PLATFORMS = ('darwin-arm64', 'ubuntu24.04-x86_64')
VERSION_FILE = 'python/mariamem/_version.py'
FIELDS = {'MAJOR', 'MINOR', 'PATCH', 'STAGE', 'SERIAL'}
# These tracked historical outputs are excluded by the Product receipt's
# public_files selector. They remain protected by the full Git tree comparison;
# this is not an exemption allowing them to change or new omissions to appear.
BASIS_OMISSIONS = {'build/go.mod', 'benchmarks/results/direct-link-consumer-experience.json'}
# Reviewed exceptions, not a blanket scripts/tests/release exclusion.
EXCEPTIONS = {
    'README.md', 'AGENTS.md', '.agents/skills/release/SKILL.md',
    '.github/workflows/check.yml', '.github/workflows/release-candidate-ready.yml', WORKFLOW,
    'benchmarks/ownedprepared/README.md', 'benchmarks/ownedprepared/test_tools.py',
    'release/baselines/v0.4.3.json', INTENT,
    'scripts/git_identity.py', 'scripts/validate_product_candidate.py',
    'scripts/runtime_validation.py', 'scripts/release_preparation_checks.py',
    'scripts/release_plan.py', 'scripts/release_prepare.py',
    'scripts/generated_release.py', 'scripts/release_generated_ci.py',
    'tests/test_git_identity.py', 'tests/test_runtime_validation.py',
    'tests/test_release_plan.py', 'tests/test_release_prepare.py',
    'tests/test_generated_release.py', 'tests/test_ci_publication_workflow.py',
}


def require(ok, message):
    if not ok:
        raise ValueError('Runtime evidence: ' + message)


def sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def read_intent(root):
    path = Path(root) / INTENT
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    require(isinstance(data, dict) and set(data) == {'version', 'repository', 'workflow', 'basis_commit', 'run_id', 'artifacts'},
            'invalid intent schema')
    require(type(data['version']) is int and data['version'] == 1, 'unknown intent version')
    require(data['repository'] == 'masahitojp/mariamem' and data['workflow'] == WORKFLOW,
            'wrong repository/workflow')
    require(isinstance(data['basis_commit'], str) and re.fullmatch('[0-9a-f]{40}', data['basis_commit']),
            'basis must be an exact commit SHA')
    require(type(data['run_id']) is int and data['run_id'] > 0, 'invalid run ID')
    require(isinstance(data['artifacts'], dict) and set(data['artifacts']) == set(PLATFORMS), 'both platforms required')
    for platform, record in data['artifacts'].items():
        require(isinstance(record, dict) and set(record) == {'id', 'zip_sha256'} and type(record['id']) is int
                and record['id'] > 0 and sha(record['zip_sha256']), 'invalid artifact identity')
    return data


def exempt(name):
    return name in EXCEPTIONS or name.startswith('docs/') or (
        name.startswith('release/NOTES-') and name.endswith('.md'))


def version_logic(source):
    tree = ast.parse(source)
    found = set()
    body = []
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id in FIELDS):
            name = node.targets[0].id
            require(name not in found and isinstance(node.value, ast.Constant), 'invalid version assignment')
            require(type(node.value.value) is (str if name == 'STAGE' else int), 'invalid version value')
            found.add(name)
        else:
            body.append(node)
    require(found == FIELDS, 'canonical version assignments missing')
    return ast.dump(ast.Module(body=body, type_ignores=[]), include_attributes=False)


def compare_inventory(basis, current, old_version, new_version):
    require(all(sha(v) for v in basis.values()), 'invalid basis inventory hash')
    require(all(sha(v) for v in current.values()), 'invalid candidate inventory hash')
    changed = sorted(n for n in set(basis) | set(current) if basis.get(n) != current.get(n))
    for name in changed:
        if name == VERSION_FILE:
            require(name in basis and name in current
                    and version_logic(old_version) == version_logic(new_version), 'version logic changed')
        else:
            require(exempt(name), 'changed unreviewed input: ' + name)
    return changed


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True).strip()


def tree(root, commit):
    output = subprocess.check_output(['git', 'ls-tree', '-r', '-z', commit], cwd=root)
    return {part.split(b'\t', 1)[1].decode(): part.split(b'\t', 1)[0].decode()
            for part in output.split(b'\0') if part}


def development_changed(root, commit, intent):
    """Genuine later code edits use normal development tests, never release reuse."""
    require_commit(root, commit)
    require_commit(root, intent['basis_commit'])
    old, new = tree(root, intent['basis_commit']), tree(root, commit)
    if any(old.get(n) != new.get(n) and n != VERSION_FILE and not exempt(n)
           for n in set(old) | set(new)):
        return True
    return version_logic(git(root, 'show', intent['basis_commit'] + ':' + VERSION_FILE)) != version_logic(
        (Path(root) / VERSION_FILE).read_text())


def fetch_product(api, intent, platform, destination):
    run = intent['run_id']
    info = api.json(f'/actions/runs/{run}')
    require(info.get('path', '').split('@', 1)[0] == WORKFLOW
            and info.get('repository', {}).get('full_name') == intent['repository'], 'untrusted run origin')
    require(info.get('status') == 'completed' and info.get('conclusion') == 'success'
            and info.get('head_sha') == intent['basis_commit'], 'run/source did not pass')
    jobs = []
    page = 1
    while True:
        batch = api.json(f'/actions/runs/{run}/jobs?per_page=100&page={page}')['jobs']
        jobs.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    for target in PLATFORMS:
        matches = [j for j in jobs if j.get('name') == 'Product contract — ' + target]
        require(len(matches) == 1 and matches[0].get('status') == 'completed'
                and matches[0].get('conclusion') == 'success', 'native job missing/failed: ' + target)
    entries = []
    page = 1
    while True:
        batch = api.json(f'/actions/runs/{run}/artifacts?per_page=100&page={page}')['artifacts']
        entries.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    pin = intent['artifacts'][platform]
    name = f"v044-product-{platform}-{intent['basis_commit']}"
    matches = [a for a in entries if a.get('name') == name]
    require(len(matches) == 1, 'missing/ambiguous Product artifact')
    artifact = matches[0]
    require(artifact.get('id') == pin['id'] and artifact.get('expired') is False
            and artifact.get('digest') == 'sha256:' + pin['zip_sha256'], 'artifact expired/identity changed')
    size = artifact.get('size_in_bytes')
    require(type(size) is int and 0 < size <= 8 * 1024 * 1024, 'oversized artifact')
    with api.request(f"/actions/artifacts/{pin['id']}/zip") as source, destination.open('wb') as output:
        written = 0
        while chunk := source.read(65536):
            written += len(chunk)
            require(written <= 8 * 1024 * 1024, 'oversized download')
            output.write(chunk)
    require(digest(destination) == pin['zip_sha256'], 'Product ZIP digest differs')


def evidence(archive, intent, platform):
    with zipfile.ZipFile(archive) as zipped:
        members = zipped.infolist()
        require(len(members) <= 2000 and sum(m.file_size for m in members) <= 32 * 1024 * 1024,
                'oversized evidence')
        names = [safe_name(m.filename.rstrip('/')) for m in members]
        require(len(names) == len(set(names)), 'duplicate ZIP member')
        require(all(stat.S_IFMT(m.external_attr >> 16) in (0, stat.S_IFREG, stat.S_IFDIR)
                    for m in members), 'special ZIP member')
        files = {m.filename: zipped.read(m) for m in members if not m.is_dir()}
    hashes = json.loads(files['SHA256SUMS.json'])
    require(set(files) - {'SHA256SUMS.json'} == set(hashes), 'incomplete checksum inventory')
    require(all(sha(h) and hashlib.sha256(files[n]).hexdigest() == h for n, h in hashes.items()),
            'evidence checksum differs')
    data = {n: json.loads(files[n]) for n in ('inputs.json', 'correctness.json', 'alpha-wheel.json',
                                            'alpha.json', 'snapshots.json', 'commands.json')}
    inputs, correct, wheel = (data[n] for n in ('inputs.json', 'correctness.json', 'alpha-wheel.json'))
    basis = intent['basis_commit']
    require(inputs['result'] == correct['result'] == 'PASS' and
            inputs['candidate_sha'] == correct['candidate_sha'] == wheel['source_commit'] == basis,
            'receipt result/source differs')
    require(inputs['contract'] == 'v044-ownedprepared-product-validation'
            and set(correct['boundaries']) == {'source/unit', 'handwritten races', 'Go real SQL/lifecycle',
                                              'Python import/isolation/lifecycle', 'installed pytest/xdist'},
            'runtime coverage incomplete')
    require(inputs['python'].startswith('3.14.') and wheel['manifest']['platform'] == platform,
            'wrong Python/native platform')
    require(sha(inputs['guest_sha256']) and sha(wheel['sha256']), 'invalid guest/wheel identity')
    require((platform == PLATFORMS[0] and inputs['machine'] == 'arm64'
             and inputs['platform'].startswith('macOS-15.')) or
            (platform == PLATFORMS[1] and inputs['machine'] == 'x86_64'
             and inputs['platform'].startswith('Linux-')), 'wrong native environment')
    build = wheel['host_buildinfo']
    goos, goarch = ('darwin', 'arm64') if platform == PLATFORMS[0] else ('linux', 'amd64')
    require(all(v in build for v in ('go1.26.8\n', 'CGO_ENABLED=0', '-trimpath=true',
                                     'GOOS=' + goos, 'GOARCH=' + goarch,
                                     'vcs.revision=' + basis, 'vcs.modified=false')), 'build settings differ')
    alpha = data['alpha.json']
    require(wheel['archive_checks_passed'] and alpha['passed'] and
            alpha['installed_files_match_wheel'] and alpha['consumer_outside_repository'] and
            alpha['native_overrides'] is False and alpha['wheel_sha256'] == wheel['sha256'],
            'installed-wheel boundary failed')
    require({r['name'] for r in alpha['runs']} == {'serial', 'parallel', 'migration', 'failure-cleanup'},
            'installed suites missing')
    require(data['snapshots.json']['passed'] and len(data['snapshots.json']['checks']) == 49,
            'Snapshot acceptance incomplete')
    commands = data['commands.json']
    require(all(c.get('exit_code') == 0 for c in commands), 'a qualification command failed')
    require({'validation-tools', 'source-unit-checks', 'runtime-integration', 'wheel-build',
             'installed-pytest', 'comparison'} <= {c['name'] for c in commands}, 'commands missing')
    return wheel['source_files_sha256'], {
        'zip_sha256': intent['artifacts'][platform]['zip_sha256'],
        'artifact_id': intent['artifacts'][platform]['id'],
        'checksums_sha256': hashlib.sha256(files['SHA256SUMS.json']).hexdigest(),
        'original_wheel_sha256': wheel['sha256'], 'guest_sha256': inputs['guest_sha256'],
    }


def validate(root, commit, api=None):
    root = Path(root).resolve()
    intent = read_intent(root)
    require(intent is not None, 'reuse intent missing')
    repository = root if (root / '.git').exists() else ROOT
    require_commit(repository, commit)
    require_commit(repository, intent['basis_commit'])
    require(git(repository, 'rev-parse', 'HEAD') == commit, 'not exact candidate checkout')
    require(not git(repository, 'status', '--porcelain'), 'candidate checkout is dirty')
    subprocess.run(['git', 'merge-base', '--is-ancestor', intent['basis_commit'], commit],
                   cwd=repository, check=True, capture_output=True)
    old_tree, new_tree = tree(repository, intent['basis_commit']), tree(repository, commit)
    for n in set(old_tree) | set(new_tree):
        if old_tree.get(n) != new_tree.get(n):
            require(n == VERSION_FILE or exempt(n), 'unreviewed tree change: ' + n)
            if n == VERSION_FILE:
                require(old_tree[n].split()[0] == new_tree[n].split()[0] == '100644', 'version type/mode changed')
    old_version = git(repository, 'show', intent['basis_commit'] + ':' + VERSION_FILE)
    require(version_logic(old_version) == version_logic((root / VERSION_FILE).read_text()), 'version logic changed')
    current = {p.relative_to(root).as_posix(): digest(p) for p in public_files(root)}
    if api is None:
        token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
        if not token and not os.environ.get('GITHUB_ACTIONS'):
            token = subprocess.check_output(['gh', 'auth', 'token'], text=True).strip()
        api = GitHub(intent['repository'], token)
    receipts = {}
    inventories = []
    with tempfile.TemporaryDirectory(prefix='mariamem-runtime-evidence-') as temporary:
        for platform in PLATFORMS:
            archive = Path(temporary) / (platform + '.zip')
            fetch_product(api, intent, platform, archive)
            inventory, receipt = evidence(archive, intent, platform)
            inventories.append(inventory)
            receipts[platform] = receipt
    require(inventories[0] == inventories[1], 'native source inventories differ')
    basis_inventory = inventories[0]
    expected_names = set(old_tree) - REPOSITORY_ONLY_FILES - BASIS_OMISSIONS
    require(set(basis_inventory) == expected_names, 'basis source inventory incomplete')
    # Authenticate the basis against Git, not just a runner's claimed hash map.
    for name, expected in basis_inventory.items():
        if old_tree.get(name) == new_tree.get(name) and name in current:
            actual = current[name]
        else:
            raw = subprocess.check_output(['git', 'show', intent['basis_commit'] + ':' + name], cwd=repository)
            actual = hashlib.sha256(raw).hexdigest()
        require(actual == expected, 'basis source hash differs: ' + name)
    changed = compare_inventory(basis_inventory, current, old_version, (root / VERSION_FILE).read_text())
    guest = json.loads((root / 'release/generated-go-inputs.json').read_text())['guest_sha256']
    require(all(r['guest_sha256'] == guest for r in receipts.values()), 'guest identity differs')
    return {'version': 1, 'result': 'PASS', 'runtime_basis_commit': intent['basis_commit'],
            'release_source_commit': commit, 'run_id': intent['run_id'],
            'intent_sha256': digest(root / INTENT), 'platforms': receipts,
            'reviewed_changed_paths': changed, 'release_source_inventory': current}


def verify_frozen(root, commit):
    if read_intent(root) is None:
        return None
    fresh = validate(root, commit)
    frozen = json.loads((Path(root) / PROOF).read_text())
    require(frozen == fresh, 'frozen runtime proof differs')
    return {k: fresh[k] for k in ('runtime_basis_commit', 'release_source_commit', 'run_id', 'platforms')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--candidate-sha', required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--github-output', action='store_true')
    parser.add_argument('--development', action='store_true',
                        help='genuine code edits run normal development checks; release never uses this')
    args = parser.parse_args()
    try:
        intent = read_intent(args.root)
        changed = bool(intent and args.development and development_changed(args.root, args.candidate_sha, intent))
        result = validate(args.root, args.candidate_sha) if intent and not changed else None
        if result and args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
        if args.github_output:
            with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
                output.write('reused=' + str(result is not None).lower() + '\n')
        print(json.dumps({'result': 'PASS' if result else 'NO REUSE INTENT',
                          'runtime_basis_commit': result['runtime_basis_commit'] if result else None,
                          'release_source_commit': args.candidate_sha}, indent=2))
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        parser.exit(1, f'Runtime evidence reuse stopped: {error}\nNo automatic runtime requalification.\n')


if __name__ == '__main__':
    main()
