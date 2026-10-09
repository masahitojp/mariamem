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

