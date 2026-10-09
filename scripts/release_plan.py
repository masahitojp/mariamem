#!/usr/bin/env python3
"""Select full qualification or authenticated exact-SHA READY reuse; never publish."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import http.client
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

from check_public import public_files
from ci_release_reuse import GitHub, WORKFLOW
from generated_release import CONTRACT, PLATFORMS, checkout, expected_names, read, require, version
from runtime_validation import read_intent, validate as validate_runtime


def ready_bundle(archive, commit, canonical):
    """Read only the aggregate receipt, never extract untrusted ZIP paths."""
    with zipfile.ZipFile(archive) as zipped:
        names = []
        for item in zipped.infolist():
            require(item.filename in {'ci-ready.json', 'SHA256SUMS', 'qualification.json'},
                    'unexpected READY member')
            require(stat.S_IFMT(item.external_attr >> 16) in (0, stat.S_IFREG),
                    'special READY member')
            require(item.file_size <= 4 * 1024 * 1024, 'oversized READY receipt')
            names.append(item.filename)
        require(len(names) == len(set(names)) and {'ci-ready.json', 'SHA256SUMS'} <= set(names),
                'missing/duplicate READY receipt')
        ready = json.loads(zipped.read('ci-ready.json'))
        require(isinstance(ready, dict), 'invalid READY receipt')
        require(ready.get('version') == 3 and ready.get('contract') == CONTRACT and
                ready.get('result') == 'READY', 'previous result is not generated-Go READY')
        require((ready.get('source_commit'), ready.get('git_tag'), ready.get('python_version')) ==
                (commit, canonical['GIT_TAG'], canonical['PYTHON_VERSION']), 'READY source/version differs')
        require(isinstance(ready.get('platforms'), dict) and set(ready['platforms']) == set(PLATFORMS),
                'READY platform evidence incomplete')
        require(isinstance(ready.get('assets'), dict) and
                set(ready['assets']) == expected_names(canonical['PYTHON_VERSION']) and
                all(isinstance(sha, str) and re.fullmatch('[0-9a-f]{64}', sha)
                    for sha in ready['assets'].values()), 'READY artifact set/hash differs')
        entries = [line.split('  ') for line in zipped.read('SHA256SUMS').decode().splitlines()]
        require(all(len(entry) == 2 for entry in entries) and
                len(entries) == len(ready['assets']) and
                {name: sha for sha, name in entries} == ready['assets'], 'READY checksums differ')
        reference = json.loads(zipped.read('qualification.json')) if 'qualification.json' in names else None
        if reference is not None:
            require(isinstance(reference, dict) and reference.get('version') == 1 and reference.get('source_commit') == commit,
                    'qualification source differs')
            for key in ('candidate_run', 'evidence_run'):
                require(type(reference.get(key)) is int and reference[key] > 0,
                        'invalid qualification run')
        return ready, reference


def previous_runs(api):
    # Search the retention window, not just workflow head_sha: older workflows
    # may have qualified an explicitly checked-out candidate on another ref.
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    for page in range(1, 11):
        runs = api.json(f'/actions/workflows/{Path(WORKFLOW).name}/runs?status=completed&per_page=100&page={page}')['workflow_runs']
        for run in runs:
            if datetime.fromisoformat(run['created_at'].replace('Z', '+00:00')) < cutoff:
                return
            yield run['id']
        if len(runs) < 100:
            return


def validate_reuse(root, commit, candidate_run, evidence_run, expected):
    # Use the candidate's own pinned guard/scripts. Scratch never contaminates
    # the checkout used for a full fallback, even after a partial failed restore.
    with tempfile.TemporaryDirectory(prefix='mariamem-ready-check-') as temporary:
        project = Path(temporary).resolve() / 'source'
        for source in public_files(root):
            destination = project / source.relative_to(root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        script = root / 'scripts/release_generated_ci.py'
        common = ['--root', str(project), '--candidate-sha', commit]
        subprocess.run([sys.executable, str(script), 'restore', *common,
                        '--candidate-run', str(candidate_run), '--evidence-run', str(evidence_run)], check=True)
        subprocess.run([sys.executable, str(script), 'guard', *common], check=True)
        require(read(project / 'build/release/ci-ready.json') == expected,
                'recomputed READY/artifact/evidence identity differs')


def plan(root, commit, operation, mode='auto', candidate_run=None, evidence_run=None,
         api=None, runs=None, validate=None):
    require(operation in {'verify', 'release'}, 'normal operation must be verify or release')
    require(mode in {'auto', 'full', 'acceptance-only', 'guard-only'}, 'unknown recovery mode')
    checkout(root, commit)
    canonical = version(root)
    # An explicit runtime-reuse intent fails closed. Never silently fall back
    # to another runtime campaign if its evidence or equivalence is invalid.
    runtime = validate_runtime(root, commit) if read_intent(root) else None
    result = {'source_sha': commit, 'version': canonical['GIT_TAG'], 'operation': operation,
              'mode': 'full', 'candidate_run': '', 'evidence_run': '', 'reused_ready_run': '',
              'runtime_reused': str(runtime is not None).lower(),
              'reason': 'no reusable exact-SHA READY'}
    if mode != 'auto':
        if mode != 'full':
            require(candidate_run and candidate_run > 0, 'recovery requires candidate_run')
        if mode == 'guard-only':
            require(evidence_run and evidence_run > 0, 'recovery requires evidence_run')
        return {**result, 'mode': mode, 'candidate_run': candidate_run or '',
                'evidence_run': evidence_run or '', 'reason': 'explicit recovery mode'}
    require(not candidate_run and not evidence_run, 'auto selects run IDs; use explicit recovery mode')
    api = api or GitHub(os.environ.get('GITHUB_REPOSITORY', 'masahitojp/mariamem'),
                        os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN'))
    validate = validate or validate_reuse
    try:
        for run in previous_runs(api) if runs is None else runs:
            try:
                with tempfile.TemporaryDirectory(prefix='mariamem-ready-discovery-') as temporary:
                    archive = Path(temporary).resolve() / 'ready.zip'
                    api.artifact(run, 'release-ready-' + commit, commit, archive)
                    ready, reference = ready_bundle(archive, commit, canonical)
                # Old full runs predate qualification.json; only accept these
                # when both handoffs and evidence validate in that same run.
                candidate = reference['candidate_run'] if reference else run
                evidence = reference['evidence_run'] if reference else run
                validate(root, commit, candidate, evidence, ready)
                return {**result, 'mode': 'guard-only', 'candidate_run': candidate,
                        'evidence_run': evidence, 'reused_ready_run': run,
                        'reason': 'authenticated READY and immutable inputs revalidated'}
            except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile,
                    subprocess.SubprocessError, http.client.HTTPException) as error:
                print(f'Cannot reuse run {run}: {error}', file=sys.stderr)
    except (ValueError, OSError, KeyError, TypeError, http.client.HTTPException) as error:
        print(f'Cannot discover READY: {error}; qualifying from source', file=sys.stderr)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--candidate-sha', required=True)
    parser.add_argument('--operation', choices=('verify', 'release'), required=True)
    parser.add_argument('--mode', choices=('auto', 'full', 'acceptance-only', 'guard-only'), default='auto')
    parser.add_argument('--candidate-run', type=int)
    parser.add_argument('--evidence-run', type=int)
    args = parser.parse_args()
    result = plan(args.root.resolve(), args.candidate_sha, args.operation,
                  args.mode, args.candidate_run, args.evidence_run)
    print(json.dumps(result, indent=2))
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
            for key, value in result.items():
                if key != 'reason':
                    output.write(f'{key}={value}\n')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as output:
            output.write(f"{result['operation']} — {result['version']} — {args.candidate_sha}\n\n"
                         f"Qualification: {result['mode']}; {result['reason']}\n")


if __name__ == '__main__':
    main()
