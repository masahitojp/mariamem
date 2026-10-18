# Default Python and multi-statement spike — Human Review

2026-10-19. **Decision: proceed to production implementation of this public
embedded-API bridge? Recommend proceeding as a production candidate, not adopting
the prototype.** Python 3.14.8 / Connector/Python 26.7.0 connects with default
capabilities and executes the tested prepared statements in both pure and C
extension modes. No client-flag removal, host interpolation fallback or MariaDB
internal API extension was needed.

The strongest objection is that **Python 3.14 compatibility is not unconditional**:
the same 26.7.0 still fails at import with Homebrew Python/OpenSSL 4.0.3.
The successful 3.14.8 environment uses OpenSSL 3.5.9. This fails before contacting
either database; another guest spike cannot fix that dependency import. Establish
an explicit consumer compatibility position before adoption. Other retained
failures and production conditions follow. The bounded investigation is complete;
this does not mean every oracle passed or one-line switching is fully implemented.
Production implementation, main adoption, Qualification and release remain
separate Human decisions.

## Scope and reviewed identities

The current request and main decision `de0e08a9c4248969a7522abebfdee8aea6ef9657`
include multi-statements and rerunning on 26.7.0. The [first spike](v06x-prepared-spike.md)
is historical evidence, not rewritten results. Cross-check the
[approved design](v06x-prepared-design.md), [wire inventory](wire-gap-inventory.md)
and [Snapshot contract](../decisions/snapshot-product-contract.md).

| Role | Identity |
| --- | --- |
| Base | `c6337f2237717ab7cb593e2dd34a6dd2ab49865b` |
| First iteration guest / host | `00859690d25730dc5ccc43581647ea3fa4863fb0` / `0e7e73e186a85eae4b8ccf4d4181c248179b6e3c` |
| Final guest source | `926365bdc853bd2a45cc00139db1b64c5d78e3e9` |
| Final tested host source | `7037f05bb279de4ce7aab622e33b13e20d7c52f0` |
| Final Wasm SHA256 (18,436,818 bytes) | `55c5d4910459c87b5e1e00eb999506acc661ea0eaa3a794662db647bd124c953` |
| Linked Wasm SHA256 | `1cfb13addafdd9e1723f401d94d2a642311771c4be33319a105617815639662d` |
| Tested host binary SHA256 | `f779d6a4e092c9dddbc9a27b7f225cf8466031105c6ce3dc7b7ef2efe7a44b89` |

Later report/status edits are documentation, not another tested runtime identity.
Developer receipts explicitly say **UNQUALIFIED**.

## Changes and observed corrections

The initial flag/reopen implementation made default Python work, but greeting
connection IDs 2/4 became SQL IDs 3/5. This FAIL was not accepted as completion.
The final path uses public `mysql_set_server_option` on the existing MYSQL/THD;
embedded CLIENT_CAPABILITIES already includes MULTI_RESULTS. Source references:
[API](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/libmysql.c#L963),
[dispatcher](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/lib_sql.cc#L108),
[defaults](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/client_settings.h).
`public-api-source-review.json` records source hashes/findings.

The guest advances engine results with mysql_more_results/mysql_next_result,
records each statement's metadata/counters/status before advancing, and retains
prior results when a later statement fails. SQL is not split by the host.
The host emits ordered packets and MORE_RESULTS; unflagged sessions still reject
batches. Standard SET_OPTION ON/OFF uses EOF replies. Passing an invalid enum to
the embedded API initially produced failure with errno 0. The host now validates
the protocol domain before calling it, returning the exact observed native
1047/08S01/Unknown command packet for unknown options. Unexpected API failure
without details closes the failure path, rather than emitting error 0 or success.
The unchanged oracle verifies the correction; the earlier FAIL is retained.

The existing FOUND_ROWS reopen path remains. Default-mode identity was established,
not every nondefault capability combination. Its affected-row behavior itself
was checked as 0 versus 1 for an unchanged UPDATE.

## Results — native macOS arm64

Named files resolve through the [checksum index](v06x-prepared-multi-spike-evidence/files.json).
Reference engine: the pinned MariaDB 12.3.3 Linux arm64 image from the first spike;
this is not native Ubuntu x86_64 evidence. Consumer is
[Connector/Python 26.7.0](https://pypi.org/project/mysql-connector-python/26.7.0/),
Python >=3.10 metadata, cp314 macOS arm64 wheel identity retained. Default flags
3383821, including MULTI_STATEMENTS, were re-derived from this installation.

| Check | Result | Evidence / limit |
| --- | --- | --- |
| Default flags, pure/C extension: multi SELECT then prepared | PASS | `validated-guest-multi.json`; valid values and reuse match native |
| Actual default mode, no use_pure/client_flags override; prepared=True, %s markers | PASS | `validated-default-mode.json`: CMySQLConnection/CMySQLCursorPrepared, int/Unicode/NULL |
| Mixed DML/SELECT; MORE_RESULTS [8,8,8,0]; first/middle errors; reuse; rollback | PASS | Same multi JSON and native control; raw single COM_QUERY, errors 1064/1146 |
| Unnegotiated batch rejected, reusable connection | PASS | Same JSON: 1064 |
| SET_OPTION ON/OFF, unknown option 1047, stable default connection ID | PASS | Same JSON; `native-unknown-option-error.json` captures exact bytes, compared by wire unit |
| FOUND_ROWS unchanged-update count | PASS | Same JSON: [0,1] |
| Repeated prepared values/types, descriptor reuse, LONG_DATA | PASS | `validated-guest-extended.json`, except its C-extension syntax case |
| Python pure writes/commit/rollback/BytesIO/close | PASS | `validated-guest-full.json` |
| Python C-extension full scenario | FAIL | Same JSON: syntax assertion expects 1064, gets 2006; preceding value/write/transaction assertions completed |
| Pure prepare syntax error | PASS | Guest/native 1064/42000 |
| C-extension prepare syntax error | FAIL in guest and native | `validated-guest-error-health.json` / `native-error-and-health.json`: 2006/HY000; next SELECT 1 succeeds. Health/parity does not satisfy the original 1064 oracle |
| Procedure multiple-result fixture | FAIL at preparation | mysql.proc absent; DROP/CREATE setup cannot complete. CALL result draining was not verified; no bootstrap expansion |
| Homebrew Python 3.14.8 / OpenSSL 4.0.3 import | FAIL before network | `homebrew314-connector267-import.log`: eager ssl.PROTOCOL_TLSv1 access; no constants injected |
| Standalone Python 3.14.8 / OpenSSL 3.5.9 import/execution, pure and C extension | PASS | Environments, Python distribution URL/binaries and wheel identities retained |
| Go DB/Tx/Conn explicit/implicit prepared; direct guest ownership/stale IDs | PASS | `validated-go-and-direct.json`; native Go control also PASS |
| Text SQL/transaction/Snapshot/three Forks/shared-host cleanup | PASS | Full `validated-development.json`, UNQUALIFIED |
| Wire unit / input-boundary unit | PASS | `validated-wire-unit.log`; `host-only-boundary-tests.log` (34 Python tests) |
| J1 negative / protected heap+mmap +/-race | Expected FAIL reproduced / protected PASS | Actual final guest functions; unchanged oracle, below |
| Native Ubuntu x86_64, performance, full framework/wheel acceptance, Qualification | SKIP | Not executed; no inferred PASS |

Gap #1's default-capability refusal is resolved in the prototype. Gap #2 is no
longer missing Python 3.14 execution evidence: the remaining import failure is
specific to the observed OpenSSL 4 build. Do not describe it as a blanket Python
3.14 incompatibility or claim updating to 26.7 alone fixed it.

## Inputs, independent generation and ownership

MariaDB `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`, lite4mariadb
`24be9371a2f6c71250a2356631ad6feab2280b02`, goccy wasm2go
`730057c146463f663e8774587bc96fb2bea91af8` and its **13 existing patches** are
unchanged. Toolchain: Go 1.26.8, LLVM 23.1.0, WASIXCC 0.4.7, sysroot
2026-07-03.1 legacy EH, Binaryen 133. Exact versions, options, archive hashes and
patch order are in `final-guest-record.json`, flags and `validated-translation.json`.
Canonical guest/source.patch and converter patches were not edited; experimental
bridge changes remain guest/experimental.patch plus owned resident/wire-core overlays.

Strict zero-fuzz application to the pinned recipe preimage matches actual builder
files and the authored include mirror (`final-strict-patch-reapplication.json`).
No generated Go was hand-edited. Independent translations have identical **52
source/data files**. Official installation on independently produced candidates,
using the same validated input record, gives **99/99 identical files including
provenance** (`validated-independent-regeneration.json`). Distinct original path
records produce distinct provenance digests; they were retained, not normalized
away. This is independent Go generation from one final Wasm build. The task's two
Wasm builds used different iteration inputs; they are not independent same-input
Wasm reproduction or release evidence.

Allocation/entry/free bodies and initial data are byte-identical to the first
prepared spike; data SHA256 is
`2c0fd2e0388841be8a0874c04b96e03a27201984c3ea2371e8cd0261648f4414`.
Only exact additional guest hashes were listed; unknown guests and body mutations
still fail closed. Actual final functions were packaged into J1: unprotected
canary 165→1, controls pass; protected heap/mmap pass four cases +/-race.
Assertions/rebased oracle bytes match round 1. Zero race reports prove no general
race freedom. After host-only validation, 98 runtime/code files and every copied
fixture input were confirmed identical; J1 evidence was reused on that explicit
identity basis (`validated-j1-reuse.json`), not rerun for an unrelated host change.

The origin checker explicitly classifies wire.go and its unit file as host-stage
inputs. Historical bytes are checked against the real guest source commit;
current host bytes are separately bound. Unit tests reject tampered old hashes,
an unclassified Go addition and guest patch changes. This avoids a new Wasm for a
Go-only validation fix, without permitting arbitrary source changes. Earlier
mount-preflight/gate failures, ID mismatch, errno-0 case and observer fixture
corrections are preserved. Historical source snippets were renamed .go.txt with
unchanged content hashes to avoid accidental mixed Go packages; relocation map
retained. No canonical release inventory/guard was weakened or repinned.

## Conditions for production and review limits

- Resolve/document exact consumer combinations and error interpretation: OpenSSL 4
  import and C-extension syntax reporting remain named FAILs; guest PASS cannot erase them.
- Retain the approved production matrix: full types/metadata/large payloads,
  schema reprepare, pool/reset/cancel/no-response lifecycle and native both-OS
  consumer checks. Cursor/FETCH and PS multiple results are not established.
- Procedure/bootstrap remains a separate concrete gap, not evidence that a CALL
  execution path is unreachable. A broader bootstrap requirement needs its own scope.
- Prototype limits (64 statements/parameters/columns, 4096-byte prepared cells,
  1024 prepared rows, buffered chains capped at 128 results) are not approved product limits.
- Ordinary CI does not execute this experimental guest. Wire/origin unit checks
  are deterministic; runtime consumer CI, canonical patch/inventory ownership,
  source/license/provenance checks and later Qualification remain adoption conditions.

Review scan: no contradiction found in the four versioned public guides, which
still describe released text-only support; no generated hand edits or public API,
version, platform or Go-minimum changes. Missing canonical adoption bookkeeping
and native Ubuntu/Qualification are explicit future conditions, not completed work.

No further guest feasibility experiment is needed to judge this default workflow.
The prior **5–10 additional engineer-day** production estimate remains provisional
(codec/types, ownership/errors/capabilities, consumer/platform checks, canonical
generation/docs), plus build/CI wait. Reserve 0.5–1 day per guest update for
reapplication and exact layout/regression review plus builds, not guaranteed
future applicability. The independent wire-relay memo is not evaluated here.

See [reproduction](v06x-prepared-multi-spike-evidence/reproduce.md) and the
[evidence index](v06x-prepared-multi-spike-evidence/files.json). Large records use
lossless gzip; original/stored hashes are recorded, with no path scrubbing.
Source/evidence are preserved before deleting disposable builds/caches/worktree.
Main integration and publication are not part of this result.
