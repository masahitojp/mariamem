# P4 lifetime/failures — finite development acceptance PASS

[CI39752222349](https://github.com/masahitojp/mariamem/actions/runs/39752222349)
PASSes at source_commit `86b89d8bef31021881449892b140b3ef5836fad9`.
Both macOS15 arm64 and Ubuntu24.04 x86_64 pass134 Python/C checks, four Go race
packages, canonical inventory and public-source guards. Together with the
existing actual-guest/native lifetime, LONG_DATA and active-exit evidence below,
this satisfies the finite P4 row. P5/P6, adoption, Qualification and release are
not complete. The [CI receipt and raw logs](v06x-prepared-p4-failures-evidence/ci/receipt.json)
separate the new component evidence from unchanged actual runtime evidence.

Basis: source_commit `a10ba205e268997bc3c8f095fad3e91fb7221996`, containing
[actual both-OS active-exit acceptance](v06x-prepared-p4-active.md) at fbe4196.
A separate documentation correction d59ec9c removes runner prefixes from the
previous factored build-info receipts, retains original/stored hashes, and fixes
the public-source check. It does not alter raw packet evidence or tested runtime.
The [receipt](v06x-prepared-p4-failures-evidence/receipt.json) records baseline,
changed source hashes, local environment and saved evidence identities. CI binds
its candidate commit separately with scripts/git_identity.py and a clean tree.

## Finite P4 coverage ledger

| Approved obligation | Existing actual guest/native evidence | Additional component evidence / remaining gate |
| --- | --- | --- |
| Go DB/Tx/Conn/Tx.Stmt, pool replacement, several physical sessions/statements | [Lifetime7](v06x-prepared-p4-lifetime.md), both OSes | No new runtime claim |
| Invalid/stale/cross-session handles; native quota and recovery | Lifetime7; unchanged quota/error/counter oracles | Existing host unwind tests remain |
| CLOSE/LONG_DATA no-response adjacency, reset/type/stream lifetime | [LONG_DATA25](v06x-prepared-long-data-pass.md), both OSes | Full append/owner allocation failure sweep now added |
| Allocation failures without half-installed owners | Actual quota ownership/recovery is measured; actual engine allocator exhaustion is not injected | Header malloc/calloc fail-at-N over nine finite success/error actions; mock public init/execute OOM, metadata/bind failures and cleanup controls; both-OS CI PASS |
| Truncated requests/results without stale state or silently shortened values | P2 native differential includes large values; existing C control reconstructs8194-byte binary value after MYSQL_DATA_TRUNCATED | Every proper prefix of a21-byte EXECUTE and a surplus byte reject before engine dispatch; full-column refetch error/short length/unexpected NULL/error flag reject; both-OS CI PASS |
| Serialization failure without partial success/retry | Actual P3 chained results/native terminal/error controls, both OSes | Every selected serializer append fails in turn, including late multi-result/wrapper/error construction; dispatcher rejects corrupt late cells/owner/status/generation with no packets and one call, with/without PS_MULTI_RESULTS; both-OS CI PASS |
| Executing-query timeout/cancel/disconnect/Close and cleanup counters | Active7, witnessed engine execution, both OSes; ordinary errors preserve target usability; fatal exits preserve siblings/baseline | No inaccessible failed-target statement count is claimed; native counter/lock/rollback and actual target storage/admission/isolation observations stay distinct |

This table identifies evidence for every item in the original P4 row.
The remaining both-OS component gate now PASSes, satisfying that stated closure
condition. There is no new unspecified investigation after this gate. The component
allocation/error results do not become real-engine OOM measurements. P5 retains
its originally specified real consumer/regression matrix, including Snapshot/
Fork/isolation/Start/Close; P6 retains full canonical generation/J1/provenance.
Nothing is deferred from P4 merely to make this table complete.

## New fault matrix

[owner-matrix.json](v06x-prepared-p4-failures-evidence/owner-matrix.json)
records9 actions: PREPARE, byte EXECUTE, truncated-blob refetch, multiple results,
LONG_DATA, RESET, CLOSE, prepare error and execute error. A successful baseline
trace enumerates owner malloc/calloc and serializer append points. Each point
then fails exactly once in its own fresh mock session. All16,884 injected
positions return no response body, rather than a partial success. Final teardown
must leave no native handle, parameter/result metadata or tracked owner/reply
allocation. A fresh session must prepare successfully afterward. This is not
reuse of a session after fatal transport failure.

Seven additional API/refetch negatives cover init, store, fetch, fetch_column
failure, short refetch, unexpected NULL and a retained truncation/error flag.
Existing tests retain prepare/metadata/bind/execute/free-result/next-result/
reset/close failure controls. Engine/storage allocation and arbitrary thread
schedules are outside this mock's reach; no all-failures or general shared-memory
proof is claimed. Counts describe these fixed traces, not all possible branches.

The normal and ASAN/UBSAN builds both run the sweep. Explicit ledgers cover
owner buffers and serializer reply buffers, native handles and metadata; this
avoids relying on LeakSanitizer availability on macOS. The mock serializer now
grows capacity geometrically while retaining the same append-failure positions.
The earlier per-character realloc version also passed, but took137 seconds under
the local combined test; the full final134-check suite takes about13 seconds.
These are harness diagnostics, not product benchmarks. Initial Go test fixtures
were corrected to provide required affected/insert fields and to avoid treating
valid LONG_DATA inline-value omission as malformed; no production rule changed.

[Two isolated source mutations](v06x-prepared-p4-failures-evidence/mutation-oracles.json)
remove prepare-entry cleanup or allow a short refetch. Both produce EXPECTED FAIL.
Only temporary header copies are changed; the original header's hash is retained.
A mutation failure is an oracle control, not a reproduced product defect.

## Verification and CI boundary

| Check | Local macOS arm64 | Ubuntu x86_64 |
| --- | --- | --- |
| Fixed scoped Python/C suite including new normal/sanitizer failure matrix |134 PASS|134 PASS (CI)|
| Go race: mysqlwire, preparedproto, guest, diagnostic |4 packages PASS|4 packages PASS (CI)|
| Two isolated negative oracle mutations |EXPECTED FAIL, both detected|Not executed locally; not a required separate platform claim|
| Canonical inventory and public-source check |PASS|PASS (CI)|
| New actual guest runtime campaign |Not run: runtime and generation inputs unchanged|Not run in this tests-only branch|

The prepared-failures branch selects only the existing both-OS unit jobs. Source
build and development-runtime jobs are SKIP for this test-only branch, with
explicit workflow conditions. The prepared-product branch retains its complete
source/runtime gate unchanged; this is not a bypass for a runtime candidate.
The relevant actual runtime evidence remains CI39747013913 at fbe4196, not a
claim that the new test-only commit was independently generated or qualified.

## Reproduction

Use Go1.26.8, Python3.14 with pytest8.4.2 and PyMySQL1.2.3, and native clang/cc.

```sh
python scripts/git_identity.py inspect HEAD
MARIAMEM_REQUIRE_PREPARED_C=1 python -m pytest -q -rA tests/test_prepared_api.py
go test -race -p 1 -count=1 ./internal/mysqlwire ./internal/preparedproto ./internal/guest ./internal/diagnostic
clang -std=c11 -Wall -Wextra -Werror -I guest tests/fixtures/prepared_api_harness.c -o /tmp/prepared-owner
/tmp/prepared-owner failure-matrix
python scripts/verify_generated_runtime.py
python scripts/check_public.py
```

The workflow retains the complete fixed134-check list and both-OS race logs.
A compiler missing from the required gate is FAIL, not silently skipped.
No main merge, version placement, tag or publication is authorized here.
