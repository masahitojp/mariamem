"""Verify public downloads against the exact accepted asset inventory.

Shared by the current generated-Go public smoke; no legacy runtime imports.
"""
import re
from common import digest


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_downloads(directory, assets):
    require({p.name for p in directory.iterdir()} == set(assets), 'published asset filenames differ')
    for name, expected in assets.items():
        path = directory / name
        require(path.is_file() and digest(path) == expected, 'published asset SHA256 mismatch: ' + name)
    lines = (directory / 'SHA256SUMS').read_text().splitlines()
    parsed = {}
    for line in lines:
        match = re.fullmatch(r'([0-9a-f]{64})  ([^/\\]+)', line)
        require(match is not None, 'invalid published SHA256SUMS line')
        value, name = match.groups()
        require(name not in parsed, 'duplicate published SHA256SUMS entry')
        parsed[name] = value
    require(parsed == {k: v for k, v in assets.items() if k != 'SHA256SUMS'},
            'published SHA256SUMS differs from accepted artifacts')
    return {name: digest(directory / name) for name in assets}



def verify_publication(record, provenance, commit, metadata, repository):
    """Permit narrower smoke only for exact final-artifact READY identities."""
    from generated_release import CONTRACT, PLATFORMS, expected_names
    require(record.get('version') == 3 and record.get('contract') == CONTRACT
            and record.get('status') == 'PUBLISHED' and record.get('source_commit') == commit
            and record.get('repository') == repository
            and record.get('git_tag') == metadata['GIT_TAG']
            and record.get('python_version') == metadata['PYTHON_VERSION'], 'publication identity differs')
    require(set(record['assets']) == expected_names(metadata['PYTHON_VERSION']) | {'SHA256SUMS'}, 'published asset contract differs')
    require(provenance.get('contract') == CONTRACT and provenance.get('source_commit') == commit
            and provenance.get('platforms') == record.get('platforms'), 'public provenance/accepted platforms differ')
    require(provenance.get('assets') == {n:h for n,h in record['assets'].items()
                                       if n != 'SHA256SUMS' and not n.endswith('-provenance.json')}, 'public provenance assets differ')
    require(set(record['platforms']) == set(PLATFORMS), 'both final-artifact platforms required')
    for platform, ready in record['platforms'].items():
        require(ready.get('version') == 3 and ready.get('contract') == CONTRACT and ready.get('result') == 'READY'
                and ready.get('source_commit') == commit and ready.get('platform') == platform
                and ready.get('git_tag') == metadata['GIT_TAG']
                and ready.get('python_version') == metadata['PYTHON_VERSION']
                and re.fullmatch('[0-9a-f]{64}', ready.get('acceptance_sha256', '')),
                'final artifact was not accepted: ' + platform)
        wheel = ready['wheel_record']
        require(record['assets'].get(wheel['wheel'].rsplit('/',1)[-1]) == wheel['sha256']
                and wheel['source_commit'] == commit, 'accepted wheel identity differs')
    return record


def verify_six_target_publication(record, provenance, sums, commit, metadata, repository):
    from generated_release import source_name, wheel_name
    from release_candidate_preview import CONTRACT, TARGETS

    package = metadata['PYTHON_VERSION']
    tag = metadata['GIT_TAG']
    assets = {source_name(package), *(wheel_name(package, target) for target in TARGETS)}
    require(set(sums) == assets | {f'mariamem-{package}-provenance.json'}, 'six-target checksum inventory differs')
    require(all(re.fullmatch('[0-9a-f]{64}', value) for value in sums.values()), 'invalid six-target asset digest')
    require((provenance.get('contract'), provenance.get('source_commit'), provenance.get('git_tag'),
             provenance.get('python_version')) == (CONTRACT, commit, tag, package),
            'six-target publication provenance differs')
    require(provenance.get('assets') == {name: sums[name] for name in assets}, 'six-target provenance assets differ')
    proof = provenance['qualification']
    attempt = proof.get('run_attempt')
    require(all(type(proof.get(key)) is int and proof[key] > 0 for key in ('run_id', 'run_attempt', 'artifact_id'))
            and proof.get('name') == f'release-candidate-preview-{commit}-attempt-{attempt}'
            and re.fullmatch('[0-9a-f]{64}', proof.get('zip_sha256', '')),
            'six-target qualification reference differs')
    if record is not None:
        require((record.get('contract'), record.get('status'), record.get('repository'),
                 record.get('source_commit'), record.get('git_tag'), record.get('python_version'))
                == (CONTRACT, 'PUBLISHED', repository, commit, tag, package), 'six-target publication record differs')
        require(record.get('qualification') == proof and set(record['assets']) == set(sums) | {'SHA256SUMS'}
                and all(record['assets'].get(name) == value for name, value in sums.items()),
                'six-target publication record assets differ')
