"""Recompute retained statistics without builds, scratch trees or identity writes."""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import statistics

LABELS = ('baseline', 'candidate')
GO_CASES = tuple(f'{case}-{mode}' for case in ('light', 'fixture', 'parallel')
                 for mode in ('fresh', 'fork'))


def verify_hashes(root):
    for name, expected in json.loads((root / 'SHA256SUMS.json').read_text()).items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'checksum mismatch: {name}')


def compact(raw):
    """Extract only the samples needed to independently recalculate the report."""
    data = {'schema': 1, 'go': {}, 'python': {}, 'resources': []}
    for case_mode in GO_CASES:
        data['go'][case_mode] = {}
        for label in LABELS:
            samples = []
            for p in sorted((raw / 'go').glob(f'plain-{case_mode}-*-{label}.json')):
                doc = json.loads(p.read_text())
                phase = {}
                for op in doc['operations']:
                    key = re.sub(r'_\d+$', '', op['name'])
                    phase[key] = phase.get(key, 0) + op['seconds'] * 1000
                samples.append(dict(source_file=p.relative_to(raw).as_posix(),
                                    suite_ms=doc['suite_product_seconds'] * 1000,
                                    phase_ms=phase))
            data['go'][case_mode][label] = samples
    for scale in ('small', 'medium'):
        data['python'][scale] = {}
        for label in LABELS:
            samples = []
            for p in sorted((raw / 'python').glob(f'plain-{scale}-*-{label}.json')):
                doc = json.loads(p.read_text())
                samples.append(dict(source_file=p.relative_to(raw).as_posix(),
                                    suite_ms=doc['whole_ms'], phase_ms=doc['times_ms']))
            data['python'][scale][label] = samples
            for p in sorted((raw / 'python').glob(f'resource-{scale}-*-{label}.json')):
                data['resources'].append(dict(source_file=p.relative_to(raw).as_posix(),
                                              **json.loads(p.read_text())))
    return data


def summarize(data):
    if data['schema'] != 1 or set(data['go']) != set(GO_CASES):
        raise ValueError('unexpected sample schema or Go cells')
    if set(data['python']) != {'small', 'medium'}:
        raise ValueError('unexpected Python cells')
    rows, phases = [], {}
    for language, cells in [('Go', data['go']), ('Python', data['python'])]:
        for cell, docs in cells.items():
            if set(docs) != set(LABELS):
                raise ValueError(f'{cell}: expected both releases')
            vals = {}
            for label in LABELS:
                samples = docs[label]
                if len(samples) != 6:
                    raise ValueError(f'{cell}/{label}: expected six ordinary samples')
                case, mode = cell.rsplit('-', 1) if language == 'Go' else (cell, 'prepared')
                stem = cell if language == 'Go' else case
                folder = 'go' if language == 'Go' else 'python'
                expected = [f'{folder}/plain-{stem}-{n}-{label}.json' for n in range(6)]
                if [d['source_file'] for d in samples] != expected:
                    raise ValueError(f'{cell}/{label}: sample order/identity mismatch')
                vals[label] = [d['suite_ms'] for d in samples]
                for d in samples:
                    if not math.isfinite(d['suite_ms']) or d['suite_ms'] <= 0:
                        raise ValueError('invalid suite duration')
                    if any(not math.isfinite(v) or v < 0 for v in d['phase_ms'].values()):
                        raise ValueError('invalid phase duration')
            a, b = [statistics.median(vals[k]) for k in LABELS]
            rows.append(dict(language=language, case=case, mode=mode,
                             baseline_ms=a, candidate_ms=b, change_percent=(b/a-1)*100,
                             slower_pairs=sum(y>x for x, y in zip(vals['baseline'], vals['candidate'])),
                             pairs=6, baseline_min_ms=min(vals['baseline']),
                             baseline_max_ms=max(vals['baseline']),
                             candidate_min_ms=min(vals['candidate']),
                             candidate_max_ms=max(vals['candidate'])))
            key = cell if language == 'Go' else 'python-' + cell
            phases[key] = {}
            for label in LABELS:
                keys = list(docs[label][0]['phase_ms'])
                if any(set(d['phase_ms']) != set(keys) for d in docs[label]):
                    raise ValueError('phase inventory mismatch')
                phases[key][label] = {
                    k: statistics.median(d['phase_ms'][k] for d in docs[label]) for k in keys}
            if language == 'Python' and cell == 'small':
                a, b = [statistics.median(vals[k][1:]) for k in LABELS]
                phases[key]['excluding_first_pair_sensitivity'] = dict(
                    baseline_ms=a, candidate_ms=b, change_percent=(b/a-1)*100)
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return {'summary.json': json.dumps(dict(rows=rows, phases=phases), indent=2)+'\n',
            'summary.csv': output.getvalue()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-dir', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--check', action='store_true', help='read-only hash and summary comparison')
    parser.add_argument('--raw-root', type=Path, help='also verify extraction from the pinned raw archive')
    parser.add_argument('--output-dir', type=Path, help='write summaries here instead of evidence-dir')
    parser.add_argument('--collect-raw', type=Path, help='collect a new run into a separate output-dir')
    args = parser.parse_args()
    if args.check and args.output_dir:
        parser.error('--check cannot write --output-dir')
    if args.collect_raw and (args.check or args.raw_root or not args.output_dir):
        parser.error('--collect-raw requires --output-dir and excludes --check/--raw-root')
    root = args.evidence_dir
    try:
        data = compact(args.collect_raw) if args.collect_raw else json.loads((root / 'samples.json').read_text())
        if args.raw_root:
            # Require the exact published archive manifest before trusting its files.
            archive = json.loads((root / 'archive.json').read_text())
            if hashlib.sha256((args.raw_root / 'SHA256SUMS.json').read_bytes()).hexdigest() != archive['manifest_sha256']:
                raise ValueError('raw archive manifest mismatch')
            verify_hashes(args.raw_root)
            if compact(args.raw_root) != data:
                raise ValueError('compact samples differ from the pinned raw archive')
        results = summarize(data)
        if args.check:
            verify_hashes(root)
            for name, content in results.items():
                if (root / name).read_bytes() != content.encode():
                    raise ValueError(f'recomputed {name} differs')
            print('PASS: read-only summary and checksum verification')
        else:
            target = args.output_dir or root
            target.mkdir(parents=True, exist_ok=True)
            if args.collect_raw:
                (target / 'samples.json').write_text(json.dumps(data, separators=(',', ':'))+'\n')
            for name, content in results.items():
                (target / name).write_text(content)
            print('Wrote summary.json and summary.csv; inputs.json remains unchanged')
    except (ValueError, KeyError, OSError, TypeError) as exc:
        parser.exit(1, f'FAIL: {exc}\n')


if __name__ == '__main__':
    main()
