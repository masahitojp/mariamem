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
