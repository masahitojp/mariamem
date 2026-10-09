#!/usr/bin/env python3
"""Authenticate runtime-only qualification; never relabel historical Product evidence."""
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
CONTRACT = 'runtime-qualification-v1'
FIELDS = {'MAJOR', 'MINOR', 'PATCH', 'STAGE', 'SERIAL'}
# Runtime receipts inventory every tracked file. Restored release platform trees
# intentionally omit these repository-only / ignored historical tracked paths.
BASIS_OMISSIONS = {'build/go.mod', 'benchmarks/results/direct-link-consumer-experience.json'}
EXCEPTIONS = {'README.md', 'AGENTS.md', '.agents/skills/release/SKILL.md', INTENT}
BOUNDARIES = {'source/unit', 'handwritten races', 'Go real SQL/lifecycle',
              'Python wire/import/isolation/lifecycle', 'memory32 traps'}


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
    require(type(data['version']) is int and data['version'] == 2, 'unknown intent version')
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
    return name in EXCEPTIONS or (name.startswith('docs/') and Path(name).suffix in ('.md', '.json', '.csv')) or (
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
            require(name in basis and name in current and
                    version_logic(old_version) == version_logic(new_version), 'version logic changed')
        else:
            require(exempt(name), 'unreviewed source change: ' + name)
    return changed


def source_inventory(root, commit):
    return {name: hashlib.sha256(subprocess.check_output(
        ['git', 'show', commit + ':' + name], cwd=root)).hexdigest()
        for name in tree(root, commit)}


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True).strip()


def tree(root, commit):
    output = subprocess.check_output(['git', 'ls-tree', '-r', '-z', commit], cwd=root)
    return {part.split(b'\t', 1)[1].decode(): part.split(b'\t', 1)[0].decode()
            for part in output.split(b'\0') if part}


def fetch_qualification(api, intent, platform, destination):
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
        matches = [j for j in jobs if j.get('name') == 'Runtime qualification — ' + target]
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
    name = f"runtime-{platform}-{intent['basis_commit']}"
    matches = [a for a in entries if a.get('name') == name]
    require(len(matches) == 1, 'missing/ambiguous runtime artifact')
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
    require(digest(destination) == pin['zip_sha256'], 'runtime ZIP digest differs')


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
    inputs = json.loads(files['inputs.json'])
    correct = json.loads(files['correctness.json'])
    commands = json.loads(files['commands.json'])
    inventory = json.loads(files['source-inventory.json'])
    basis = intent['basis_commit']
    require(inputs.get('contract') == correct.get('contract') == CONTRACT
            and type(inputs.get('version')) is int and type(correct.get('version')) is int
            and inputs['version'] == correct['version'] == 1,
            'historical/unknown qualification contract')
    require(inputs.get('result') == correct.get('result') == 'PASS'
            and inputs.get('candidate_sha') == correct.get('candidate_sha') == basis,
            'receipt result/source differs')
    require(set(correct.get('boundaries', [])) == BOUNDARIES, 'runtime coverage incomplete')
    require(inputs.get('native_platform') == platform and inputs.get('python', '').startswith('3.14.')
            and inputs.get('go_version') == 'go version go1.26.8 ' +
                ('darwin/arm64' if platform == PLATFORMS[0] else 'linux/amd64'), 'wrong toolchain/platform')
    env = inputs.get('environment', {})
    require((platform == PLATFORMS[0] and env.get('system') == 'Darwin'
             and env.get('architecture') == 'arm64' and env.get('product_version', '').startswith('15.'))
            or (platform == PLATFORMS[1] and env.get('system') == 'Linux'
                and env.get('architecture') == 'x86_64' and env.get('distribution') == 'ubuntu'
                and env.get('version_id') == '24.04'), 'wrong native environment')
    require(sha(inputs.get('guest_sha256')) and sha(inputs.get('git_tree_sha256')),
            'invalid guest/tree identity')
    require(isinstance(inventory, dict) and inventory and all(sha(v) for v in inventory.values()),
            'invalid source inventory')
    require(digest_bytes(files['source-inventory.json']) == inputs.get('source_inventory_sha256'),
            'inventory binding differs')
    require(isinstance(commands, list) and len(commands) == 2
            and {c.get('name') for c in commands} == {'source-unit-checks', 'runtime-integration'},
            'commands missing/duplicated')
    for c in commands:
        expected = 'check' if c['name'] == 'source-unit-checks' else 'integration'
        require(type(c.get('exit_code')) is int and c['exit_code'] == 0 and c.get('argv', [])[1:] == ['scripts/verify.py', expected],
                'qualification command failed/substituted')
    harness = inputs.get('harness_sha256', {})
    require(harness and all(inventory.get(n) == h for n, h in harness.items())
            and 'scripts/verify.py' in harness and 'scripts/validate_product_candidate.py' in harness
            and WORKFLOW in harness, 'harness identity incomplete/differs')
    return inventory, {
        'zip_sha256': intent['artifacts'][platform]['zip_sha256'],
        'artifact_id': intent['artifacts'][platform]['id'],
        'checksums_sha256': digest_bytes(files['SHA256SUMS.json']),
        'guest_sha256': inputs['guest_sha256'], 'git_tree_sha256': inputs['git_tree_sha256'],
        'contract': CONTRACT,
    }


def digest_bytes(value):
    return hashlib.sha256(value).hexdigest()


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
            if n in old_tree and n in new_tree:
                require(old_tree[n].split()[:2] == new_tree[n].split()[:2], 'source type/mode changed: ' + n)
    old_version = git(repository, 'show', intent['basis_commit'] + ':' + VERSION_FILE)
    require(version_logic(old_version) == version_logic((root / VERSION_FILE).read_text()), 'version logic changed')
    current = source_inventory(repository, commit)
    actual = {p.relative_to(root).as_posix(): digest(p) for p in public_files(root)}
    require(set(actual) == set(new_tree) - REPOSITORY_ONLY_FILES - BASIS_OMISSIONS,
            'candidate source inventory incomplete/untracked')
    require(all(current.get(n) == h for n, h in actual.items()), 'candidate source files differ from Git')
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
            fetch_qualification(api, intent, platform, archive)
            inventory, receipt = evidence(archive, intent, platform)
            inventories.append(inventory)
            receipts[platform] = receipt
    require(inventories[0] == inventories[1], 'native source inventories differ')
    basis_inventory = inventories[0]
    require(basis_inventory == source_inventory(repository, intent['basis_commit']),
            'basis source inventory incomplete/hash differs')
    tree_hash = digest_bytes(json.dumps(old_tree, sort_keys=True, separators=(',', ':')).encode())
    require(all(r['git_tree_sha256'] == tree_hash for r in receipts.values()), 'basis Git tree differs')
    changed = compare_inventory(basis_inventory, current, old_version, (root / VERSION_FILE).read_text())
    guest = json.loads((root / 'release/generated-go-inputs.json').read_text())['guest_sha256']
    require(all(r['guest_sha256'] == guest for r in receipts.values()), 'guest identity differs')
    return {'version': 2, 'contract': CONTRACT, 'result': 'PASS', 'runtime_basis_commit': intent['basis_commit'],
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
    args = parser.parse_args()
    try:
        intent = read_intent(args.root)
        result = validate(args.root, args.candidate_sha) if intent else None
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
