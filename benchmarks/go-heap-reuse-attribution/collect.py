"""Publish complete text observations; retain eight original small CPU/allocation profiles."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    w = a.workspace.resolve()
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    receipt = json.loads((w / 'evidence/receipt.json').read_text())
    profiles = {row['name'] + '.pprof': row['profile_sha256'] for row in receipt['cells'] if row['profiled']}
    profiles.update({row['name'] + '-allocs.pprof': row['alloc_profile_sha256'] for row in receipt['cells']})
    ledger = dict(normalization='Task/repository/home path prefixes; .log becomes .txt; LF line endings and trailing whitespace removal. Numeric observations and sample stacks are unchanged.',
                  collector_sha256=sha(Path(__file__).read_bytes()), files=[])
    for source in sorted((w / 'evidence').rglob('*')):
        if not source.is_file():
            continue
        assert not source.is_symlink()
        rel = source.relative_to(w / 'evidence')
        before = source.read_bytes()
        if source.suffix == '.pprof':
            assert profiles[source.name] == sha(before)
            assert source.with_name(source.stem + '-raw.txt').is_file()
            ledger['files'].append(dict(source=rel.as_posix(), stored=None, original_sha256=sha(before),
                reason='Original binary CPU/allocation profile retained in local compact evidence. Complete sample/location/mapping text is public in the matching -raw.txt file.'))
            continue
        assert source.suffix in ['.json', '.txt', '.csv', '.log']
        target = rel.with_suffix('.txt') if rel.suffix == '.log' else rel
        content = before.decode()
        for prefix, replacement in [(str(w), '<WORKSPACE>'), (str(w.parents[2]), '<REPOSITORY>'), (str(Path.home()) + '/', '<HOME>/')]:
            content = content.replace(prefix, replacement)
        had_final_newline = content.endswith(('\n', '\r'))
        content = '\n'.join(line.rstrip() for line in content.splitlines()) + ('\n' if had_final_newline else '')
        after = content.encode()
        dest = out / target
        dest.parent.mkdir(parents=True, exist_ok=True)
        assert not dest.exists()
        dest.write_bytes(after)
        ledger['files'].append(dict(source=rel.as_posix(), stored=target.as_posix(),
            original_sha256=sha(before), stored_sha256=sha(after), normalized=before != after))
    assert sum(row['stored'] is None for row in ledger['files']) == 8
    (out / 'preservation.json').write_text(json.dumps(ledger, indent=2) + '\n')
    for row in ledger['files']:
        if row['stored']:
            assert sha((out / row['stored']).read_bytes()) == row['stored_sha256']
    print('PASS: all public observation hashes checked; eight original binary profiles retained')


if __name__ == '__main__':
    main()
