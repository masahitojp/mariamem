"""Preserve compact observations and a before/after hash ledger for public paths."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    w = args.workspace.resolve()
    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    substitutions = [(str(w), '<WORKSPACE>'),
                     (str(w.parents[2]), '<REPOSITORY>'),
                     (str(Path.home()) + '/', '<HOME>/')]
    manifest = dict(normalization='Replace task/repository/home path prefixes; .log becomes .txt; CSV CRLF becomes LF. Numeric observations and source/binary hashes unchanged.',
                    collector_sha256=digest(Path(__file__).read_bytes()), files=[])
    for source in sorted((w / 'evidence').rglob('*')):
        if not source.is_file():
            continue
        assert not source.is_symlink(), source
        assert source.suffix in ['.json', '.txt', '.csv', '.log'], source
        relative = source.relative_to(w / 'evidence')
        target = relative.with_suffix('.txt') if relative.suffix == '.log' else relative
        assert not (destination / target).exists(), target
        before = source.read_bytes()
        content = before.decode()
        for actual, replacement in substitutions:
            content = content.replace(actual, replacement)
        if source.suffix == '.csv':
            content = content.replace('\r\n', '\n')
        after = content.encode()
        (destination / target).parent.mkdir(parents=True, exist_ok=True)
        (destination / target).write_bytes(after)
        manifest['files'].append(dict(source=relative.as_posix(), stored=target.as_posix(),
            original_sha256=digest(before), stored_sha256=digest(after), normalized=before != after))
    (destination / 'preservation.json').write_text(json.dumps(manifest, indent=2) + '\n')
    assert len({r['stored'] for r in manifest['files']}) == len(manifest['files'])
    for row in manifest['files']:
        assert digest((destination / row['stored']).read_bytes()) == row['stored_sha256']
    print(f'PASS: preserved and verified {len(manifest["files"])} compact evidence files')


if __name__ == '__main__':
    main()
