# Local correctness receipt, 2026-11-10

**PASS on local macOS27.2 arm64 / Go1.27.3**, exact source_commit
`6ee47f83326e138f0b83fb975def0b77d87f464b`. This is not Ubuntu or hosted macOS
acceptance, a new performance measurement, or product adoption. Later commits
add only this receipt; no runtime/source acceptance is relabelled.

| Boundary | Result |
|---|---|
| Full initial256MiB generated layout, deterministic regeneration | PASS; same initial-byte hash as the prior prototype |
| Omitted init-flag / wrong memory hash / dropped state / source identity | All4 rejected |
| Mapping, whole-memory equality, child isolation, Grow/guard, worker retirement | PASS; no constructor test skipped |
| Concurrent acquire/Close, retained failure ownership, independent new owner | PASS |
| Pipe Fresh/Fork × P1/P4,8 children/case | All32 child SQL/isolation/cleanup oracles PASS |
| Wrong-seed Fresh/Fork | Both fail as intended; cleanup PASS |
| Final FD, mapping and scratch ownership | No debt |

Attempt1 failed at dependency download because sandbox DNS denied access.
Attempt2 reached successful Fresh SQL and cleanup but the new collector wrongly
expected a version field on every child; the established probe records it only
on index0. The collector was corrected, then the entire fixed6-case check reran
at the SHA above. Both attempts retain their source context in the archive.
No product/runtime code was changed for that correction.

`summary.json` is the readable identity/result index. `evidence.json.gz` contains
JSON keyed by the original small evidence filenames, including all6 DB reports,
unit logs, generator controls, input/binary identities and failed-attempt records.
It is lossless for these selected receipts, normalized only for workspace paths.
Verify each file against `SHA256SUMS.json`; decompress the archive with Python's
`gzip` module. Reproduce with `benchmarks/issue123layout/verify.py` at the measured
source. The hosted matrix is submitted separately; its status is not inferred
from this local PASS.
