# P4 LONG_DATA and parameter metadata: both-OS development PASS

[CI39729456821](https://github.com/masahitojp/mariamem/actions/runs/39729456821)
completes all five jobs successfully at source_commit
`fba09f6356fd13aa088f67a2e2c17cad6729ec7e`. The
[receipt and raw case evidence](v06x-prepared-long-data-pass-evidence/receipt.json)
confirm the following on macOS15 arm64 and Ubuntu24.04 x86_64:

| Gate | Result on each OS |
| --- | --- |
| Exact new guest build, formal Wasm→Go installation/compilation and existing SQL/transaction/Snapshot/Fork/Close smoke | PASS |
| Installed exact function/data/TLS/init binding and20 rejection/mutation cases | PASS |
| P1 lifecycle/native metadata controls | PASS |
| All72 P2 cases (22 EXECUTE,13 TIME,20 extended,15 repair,2 unsigned) | PASS, native comparison |
| Minimal CALL and all14 P3 cases | PASS, native comparison |
| First7 P4 lifetime/Go DB/Tx/Conn/pool cases | PASS, native comparison |
| All25 LONG_DATA cases | PASS, strict native comparison; different_cases=[] |
| Following QUERY and no-response adjacency for every LONG_DATA case | PASS |
| Active connections after each LONG_DATA case / temporary cleanup | 0 / removed |
| Python/C ownership/input checks, including sanitizers |122 PASS |
| Go protocol/guest race packages |3 PASS |

## What this closes

The [previous failure](v06x-prepared-param-metadata.md) reproduced91 incorrect
parameter names across24 cases on each OS. All raw PREPARE parameter/result
metadata, execution/error traces and following-query controls now match the
unchanged native25-case fixture byte-for-byte. The original comparator and
native packets were not normalized, narrowed or replaced. This closes that
observed metadata defect and LONG_DATA's development acceptance gate.

The accepted development input remains guest SHA256
`8f6177627855232d096cfb3987d94e35c19fc4fc0c7f32ca8c69ff9fd4990a40`.
[Binding/converter/layout evidence](v06x-prepared-param-metadata-binding/reproduce.md)
records the fixed13 converter patches and exact BSS+64 owner binding. Both CI
hosts use this guest. Each binary and installed generated inventory is recorded
separately; platform-specific binary identity equality is not claimed.

The actual coverage includes binary/NUL/Unicode chunks, empty-vs-NULL precedence,
inline value omission and cached type transitions, independent statement streams,
invalid-index deferred errors, rejected numeric/temporal/NULL/decimal stream
arguments, accepted string/blob types, RESET/CLOSE/no-response adjacency,
index64, aggregate payload beyond1MiB and native1105 limit/error/reset recovery.
The C mock's allocation failure controls remain mock ownership evidence, not
actual embedded allocation-failure injection. Earlier documented diagnostic-area/
internal counter differences are not erased by these PASS results.

## Evidence identity and storage

Both CI clean-source identities match the complete tracked inventory at fba09f6.
Installed host source differs only within internal/generatedgo and the formal
internal/runtimekind/kind.go guest identity substitution, whose exact content
hash was checked against scripts/dev_guest.py's replacement. Canonical files in
the repository were not regenerated or edited by this reporting task.

To avoid saving three identical source maps in each development receipt,
[source-identity.json](v06x-prepared-long-data-pass-evidence/source-identity.json)
is stored once. Each platform's development-summary.json retains generated/raw
inventories, binary/toolchain/input identities, original receipt hash, references
to that shared clean-source map, and the complete installed-host delta. Rebuild
the host inventory by copying files_sha256 and applying that delta (null removes
a path). This is a factored representation, not an original-byte JSON copy.
Only runner prefixes in build-info/log strings are scrubbed; raw packet JSONs
retain their original bytes, with original/stored hashes in log-storage.json.
The saved-file receipt hashes all retained evidence.

## Remaining authorized work

**P4 is not complete.** Next is the bounded executing-query cancellation/timeout/
disconnect slice, followed by the remaining failure/resource cleanup matrix.
Idle QUIT/EOF and mock failure cleanup do not substitute for those active-query
paths. Preserve native error/timing/connection ownership controls and prove the
next connection or pooled reprepare remains usable where applicable.

P5 still needs the remaining real Go/Python prepared consumer acceptance and
regressions. P6 still needs canonical adoption/build inputs, independent
regeneration, complete J1 closure, licenses/provenance/inventory/release guards.
Neither full release Qualification nor production readiness is claimed here.
No main merge, target-version change, tag or publication is authorized by this
CI result. This report changes documentation/evidence only; no unchanged runtime
rebuild or extra CI campaign is needed just to store it.
