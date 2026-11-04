# Issue53 fixed-exit evidence — CI41761661883

Tested source_commit: `c53771cd9f653f971fdfa677105d46f6787298f9`.
[Hosted verify run](https://github.com/masahitojp/mariamem/actions/runs/41761661883),
operation=verify/mode=auto: SUCCESS. This is candidate evidence, not adoption,
a new version selection, tag or publication. Old run/source receipts are unchanged.

- `assessment.json`: eighteen fixed-row technical dispositions, limitations and
  non-doc tree fingerprint. Human adoption is PENDING.
- `matrix.json`: four OS/Python cells and actual installed source/clean/cap checks.
- `ci-status.json`: authenticated run/job identities and conclusions.
- `receipt-index.json`: ten GitHub artifact ZIP digests checked at acquisition;
 48 selected member identities, original hashes and sizes.43 small receipts/logs
  have published text in `receipts.json`; the five large nested guard/acceptance
  reports are checked projections in `guard-summary.json`, not retained originals.
- `receipts.json`: maps `artifact_id/member` to the selected published UTF-8 text.
  Only standard CI checkout/home prefixes are replaced with `<checkout>` /
  `<ci-home>`. Original and published digests remain separate; SQL, errors,
  assertions, source IDs and result values are not normalized. These are not
  represented as byte-identical original downloads.
- `core-summary.json`: checked invocation/outcome excerpts with CI checkout-prefix
  normalization, original full-log hashes and job links. Full logs are not copied.
- `SHA256SUMS.json`: checksums of these retained files (excluding itself).

The receipt selection retains installed Live/owned E2E results and provenance,
Fork-limit unit/runtime logs, G1 physical/mutation summaries, D1 serial/xdist
assessments and inputs, plus the feature gate. It excludes binaries, venvs,
build/cache trees, unrelated timing data and repetitive full guard inventories.
The source-bound guards were checked before projection: source matches, READY,
acceptance-member hash matches, GORM32/SQLAlchemy44 and all named steps pass, and
wheel hashes agree with the installed receipts and feature/aggregate assets.
The0.6.0 filenames reflect unchanged candidate metadata, not a new0.6.0 release.

Verify the retained set from this directory with Python's standard library:

```sh
python3 - <<'PY'
import hashlib, json
from pathlib import Path
root = Path('.')
for name, expected in json.loads((root/'SHA256SUMS.json').read_text()).items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest() == expected, name
index = json.loads((root/'receipt-index.json').read_text())
records = json.loads((root/'receipts.json').read_text())
for member in index['members']:
    if member['retained_published']:
        key = str(member['artifact_id'])+'/'+member['member']
        assert hashlib.sha256(records[key].encode()).hexdigest() == member['published_sha256'], key
matrix = json.loads((root/'matrix.json').read_text())
assert len(matrix['rows']) == 4 and all(row['result'] == 'PASS' for row in matrix['rows'])
assessment = json.loads((root/'assessment.json').read_text())
assert len(assessment['fixed_rows']) == 18
assert all(row['result'] == 'TECHNICAL_PASS' for row in assessment['fixed_rows'])
print('PASS: retained checksums,48 selected identities, four cells and18 fixed rows')
PY
```

Full original ZIP digests can be checked while GitHub retains the artifacts by
fetching each indexed `archive_download_url` with authenticated `gh api` and
comparing SHA256 with `digest`. The byte-exact original member hashes are also
indexed. The local acquisition checked all ten; offline verification of normalized
text does not independently reproduce the original ZIP download.

The evidence/wording commit accompanying the adoption review has no product
change. Its non-doc tree must match c53771cd; the review does not rename this
receipt to that commit or assume later main changes are tested by it. See the
[adoption review](../../issue53-fork-limit-adoption-review.md) for the decision,
critical-path inspection, prior conditions and CI blind spots.
