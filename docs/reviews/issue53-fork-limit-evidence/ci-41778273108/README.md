# Issue53 corrected-candidate evidence — CI41778273108

Tested source_commit: `cddd8dcbd6d664171907ffc1769b83e472640875`.
[Hosted run](https://github.com/masahitojp/mariamem/actions/runs/41778273108),
operation=verify/mode=auto: SUCCESS. Human adoption, merge and release remain pending.
This is new evidence after G1–G3/P1–P6; the older receipt directory is unchanged.

- `assessment.json`: eighteen fixed rows, correction dispositions and tested
  non-doc tree fingerprint; accompanying docs-only changes must preserve it.
- `matrix.json`: four OS/Python cells;105 ownership/transport tests,9 actual
  guest cases, installed Live/owned E2E and D1 serial20/xdist15 per cell.
- `receipt-index.json`:10 downloaded artifact ZIP digests checked,48 selected
  member identities/hashes.43 published texts are in `receipts.json`;5 large
  nested guard reports are checked projections in `guard-summary.json`.
- `receipts.json`: UTF-8 receipt mapping. Only standard CI checkout/home prefixes
  are normalized; original and published hashes are distinct. SQL, error,
  assertion, source and result bytes are not normalized.
- `core-summary.json`: selected invocation/result lines and original full-log
  hashes. Native forklimit package PASS is visible; individual syscall-test skip
  decisions are not visible in nonverbose output. No physical-RAM byte claim.
- `ci-status.json`: source-bound run/job IDs and conclusions (33 success,3 skip).
- `SHA256SUMS.json`: retained-file hashes, excluding itself.

Source-bound guards were checked before projection: READY, exact source,
acceptance-member hash, GORM32/SQLAlchemy44, all named steps, and matching wheel
assets across aggregate/installed results. No binaries, wheels, venvs, cache
outputs or full repetitive logs are retained. Old0.6.0 filenames reflect existing
metadata, not a new version selection or authorization to republish0.6.0.

Verify this retained set from this directory:

```sh
python3 - <<'PYCODE'
import hashlib, json
from pathlib import Path
p = Path('.')
for name, digest in json.loads((p/'SHA256SUMS.json').read_text()).items():
    assert hashlib.sha256((p/name).read_bytes()).hexdigest() == digest, name
records = json.loads((p/'receipts.json').read_text())
for m in json.loads((p/'receipt-index.json').read_text())['members']:
    if m['retained_published']:
        key = str(m['artifact_id'])+'/'+m['member']
        assert hashlib.sha256(records[key].encode()).hexdigest() == m['published_sha256']
matrix = json.loads((p/'matrix.json').read_text())
assert len(matrix['rows']) == 4 and all(r['result'] == 'PASS' for r in matrix['rows'])
PYCODE
```
