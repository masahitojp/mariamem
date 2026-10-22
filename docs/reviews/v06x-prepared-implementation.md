# Prepared implementation — staged progress, not adoption complete

The Human authorized implementation of the
[production design](v06x-prepared-product-design.md) after its review. The complete
P1–P6 scope is retained. This is a progress record and CI handoff, **not another
request to approve implementation and not a product-adoption review**.

Baseline main source_commit22a8c64305e706408ebcd54cfd7ecc45426802ad;
approved design commit00c2e18e2d74f61d169177e1b81ae2571f71fcea.
Work lives on experiment/prepared-product. Existing root untracked user files
are preserved. Workspace policy:24GiB maximum,8GiB free-space floor; task caches
and build outputs stay disposable.
The EXECUTE source preflight is on its child branch experiment/prepared-execute;
it returns to prepared-product only after the new guest's exact binding review.

## P1 source implementation

- New authored guest/prepared_api.inc owns dynamic MYSQL_STMT entries, physical
  session generations, prepare/metadata/reset/close and native destruction before
  MYSQL close. IDs/counts use protocol widths, not prototype64-element arrays.
- Versioned binary internal envelope on guest opcode5; opcode4 remains text
  COM_SET_OPTION. Magic/version/length/generation/handle validation is fail-closed.
  Ready/open explicitly list only the implemented operations22/25/26. EXECUTE and
  LONG_DATA are not advertised as implemented.
- scripts/prepare_guest.py copies/binds the authored owner and includes it after
  wire_core, before resident. No insertion into upstream lite4mariadb.c and no
  canonical source.patch/converter changes are introduced.
- internal/preparedproto owns bounded envelopes and a session-local registry.
  Numeric wire IDs may match in different sessions; mappings cannot cross their
  owning generation. Removal/clear/ID exhaustion cannot resurrect a stale entry.
- Host PREPARE metadata serializer and schema/identity validation were initially
  components only. The continuation now connects PREPARE/RESET/CLOSE to each
  physical session's registry. Metadata is checked before committing a public ID;
  rejected metadata closes the native handle. CLOSE uses a deadline-bound internal
  call without the query read-ahead monitor or a client reply. The final successful
  MYSQL open supplies the generation, including FOUND_ROWS reopen.
- This intermediate branch still keeps the old canonical guest and its unsupported
  PREPARE test. An absent prepared advertisement on that old guest retains the old
  behavior; malformed or mismatched nonzero advertisements fail closed. P6 must
  remove the legacy-guest transition when adopting the complete prepared runtime;
  P5 must replace the historical unsupported assertion with execution acceptance.
- An internal typed-envelope overhead allowance preserves the full1MiB SQL input
  while normal text request limits remain unchanged. Public packet limits are
  not raised. No generated Go is hand-edited or repinned in this stage.

## Initial P1 component verification at c63b563

| Evidence | Local result | What it does not establish |
| --- | --- | --- |
| C ownership/failure harness, ordinary + ASAN/UBSAN | PASS | Mock public API, not embedded engine semantics or new guest execution |
| >64 handles/parameters/columns; generation/closed handle negatives; prepare/metadata/allocation/late response-failure unwind | PASS in the harness | No capacity/performance promise and no proof of actual native metadata equivalence |
| Go preparedproto registry/envelopes with race | PASS | Serial per-session registry is not a concurrent map API |
| Host PREPARE metadata/error/malformed-response tests with race | PASS | Pinned generic descriptor still needs the expanded actual guest/native matrix |
| Guest request budget tests and existing package tests with race | PASS | Tests compile/run against the current checked-in canonical guest, not the new C overlay |
| Helper/source/J1 input tests plus C harness |46 PASS | Existing J1 checks remain bound to the old canonical artifact; new guest binding is pending |
| New guest source compilation and both-OS P1 units | PASS at c63b563 in [39424820005](https://github.com/masahitojp/mariamem/actions/runs/39424820005) | Single development build is UNQUALIFIED; never independent same-input source reproduction |

[Local receipt](v06x-prepared-p1-evidence/receipt.json) binds tested owner/test
hashes, actual tool versions and the four saved unit transcripts.

No existing failure oracle is weakened. Native compile success established
actual header/link availability, not completed P1 runtime semantics. The new C
owner's native MariaDB behavior, expanded parameter descriptors, actual worker
isolation, fresh guest identity/layout and end-to-end wire PREPARE still need
verification. P1 is therefore **partial**, not complete.

## P1 continuation: native control and development runtime gate

The completed source CI produced guest SHA256
`c42f1c64de3116a1552b43b76bb5c6f22053936486177c0eecdae986bfd2bdb8`
(18,390,895 bytes) from source_commit c63b5638f25dcd14d8beb403b8d6690d06d8e654.
The guest/source.patch, all authored C overlays, converter pin and13 patches are
unchanged in this continuation. A newly checksum-bound translation was produced
locally; generated Go was not hand-edited or installed into canonical source.

The [continuation evidence](v06x-prepared-p1-continuation/receipt.json) records the
source CI, artifact/translation identities, native control and local results.
See its [reproduction steps](v06x-prepared-p1-continuation/reproduce.md).
The expanded [native descriptor fixture](../../tests/fixtures/prepared-p1-native.json)
covers SELECT placeholders, typed expressions, DML, CALL, zero parameters and65
parameters/columns (71 parameter descriptors total). The unchanged generic native
descriptor matches all those native parameter cases. Native12.3.3 also passed70
simultaneously live handles, RESET, CLOSE→PING without an intervening read/sleep,
closed/cross-session ID rejection, prepare-without-DML-execution, syntax1064 with
a healthy following query, and FOUND_ROWS connections. This is a **Linux arm64
MariaDB container reference on macOS**, not a macOS-native server or new-guest PASS.
Image digest and exact fixture hashes are in the receipt.

The wire error probe preserves the raw errno **and SQLSTATE**, rather than relying
only on a driver exception. Unknown CLOSE followed by PING also retains an active
transaction started through text SQL. Ready and final-open prepared advertisements
must agree before any prepared command is accepted.

The installer has a candidate-only **single-guest** rebinding for that Wasm. Its
three complete function hashes remain hard checks; there is no relocation-tolerant
runtime matcher or alternate guest allowlist. Reviewed exact preimages are in
[prepared-p1-binding](../../tests/fixtures/prepared-p1-binding/identity.json).
Relative to the routine baseline: Fn131 is identical; Fn153 changes only absolute
addresses by+704; Fn214 has the same address relocation and copies505 rather than
497 initialized TLS bytes. Segment2 actually contains505 bytes. The full data/TLS
hashes and every changed literal are recorded, without treating arbitrary literal
changes as acceptable. This preserves the existing pre-allocator handoff and
mutation rejection. It **does not complete P6's full closure review, J1 failure
oracle/control campaign or independent canonical reproduction**.

Canonical generated files and release ledgers intentionally remain the prior
routine guest at this stage. Consequently the newly bound installer rejects
attempts to regenerate that old guest: do not mistake the old canonical inventory
check's PASS for successful installation of the new candidate. During this
transition, binding mutation unit tests use exact reviewed converter fixtures;
the new development CI repeats them against its freshly installed runtime and
compares the installed functions/data to those fixtures before the P1 wire probe.
No output or canonical provenance was refreshed to hide that intermediate state.

The expanded P1 CI builds the same fixed guest afresh at its own exact commit,
uses the formal **UNQUALIFIED development** translation/adapter/installer route,
runs the existing SQL/transaction/Snapshot/Fork/Close smoke, then executes the new
wire/native differential probe on macOS arm64 and Ubuntu x86_64. At that continuation's
submission, its results were pending; the corrected outcome is recorded below.
It is not Qualification, full P1–P6 acceptance,
or main-adoption approval.

## P1 corrected development gate — confirmed

[CI39540250744](https://github.com/masahitojp/mariamem/actions/runs/39540250744)
passed all five jobs at source_commit
`349609523b4d0a2640a0da28b7c30295ee486433`. Both macOS arm64 and Ubuntu x86_64
saved runtime.json with `result=PASS` and `native_metadata=PASS`, covering the six
P1 lifecycle/error/ownership checks and all140 descriptors against the unchanged
native fixture. Both also passed the development SQL/transaction/Snapshot/Fork/
Close smoke, installed binding check and7 mutations. The source guest hash remains
`c42f1c64de3116a1552b43b76bb5c6f22053936486177c0eecdae986bfd2bdb8`.

This closes the reported P1 development metadata failure. It is not P2 execution,
independent reproduction or final acceptance. Historical failures below retain
their original commits/results. The [continuation receipt](v06x-prepared-p2-codec-evidence/receipt.json)
retains the new job links, artifact hashes and runtime result.

## P2 initial codec component — in progress

`internal/preparedproto/values.go` adds a client EXECUTE decoder, an explicit
internal typed-value payload and binary result-row encoder. Integers/floats remain
little-endian bytes, decimal/string/blob values remain exact bytes, and temporal
bodies retain components without Go calendar/timezone conversion. Internal flags
distinguish NULL from an empty value. Counts/lengths and envelope/packet budgets
are checked before output allocation; type reuse returns a candidate descriptor
cache without mutating the committed cache on malformed input. Binary result
NULL bits use their separate two-bit offset.

The [19 input vectors](../../tests/fixtures/prepared-p2-values.json) are shared by
Go tests and a reusable [raw-wire probe](../../tests/v06_prepared_p2_probe.py).
The [native capture](../../tests/fixtures/prepared-p2-native.json) covers those
inputs plus an8,194-byte binary value,1,500 rows and65 columns, including repeated
execution without resending descriptors. It was collected from the same pinned
MariaDB12.3.3 Linux arm64 image on Docker Desktop/macOS, **not a macOS-native
MariaDB build or a new guest run**. A second native replay matched the saved
capture. Row encoder tests compare bytes to this capture, not self-round-trips
alone. Native FLOAT evaluation canonicalizes negative zero to positive zero;
input decoding preserves the input sign bit, while result encoding must use the
engine-returned value. DOUBLE NaN payload bytes in this named native case were
preserved. These observations are not universal engine/type promises.

Focused race tests and a15-second bounded fuzz run passed (119,453 fuzz executions
in that run; not a completeness claim). Tests include cut/trailing/overflowed
lengths, invalid descriptors, temporal shapes, NULL bitmap boundaries, cache
replacement/reuse, the exact1MiB client payload and32MiB-minus-header internal
boundaries. SQL calendar/range validation remains engine-owned.

**P2 is not complete.** These components are not connected to Serve or advertised
by the guest. Native MYSQL_BIND/MYSQL_TIME input binding, typed fetching and
fetch_column truncation recovery, integration with current metadata, DML/status/
warnings, reprepare, and actual guest/native differential acceptance are still
required. Unusual parameter codes versus their result-column representation also
need explicit native/API mapping; a shared byte shape alone does not prove that
mapping. LONG_DATA omission/precedence remains P4. No C overlay, generated Go,
canonical input, capability, supported operation or public API changes here.

## Remaining authorized work and historical failures

### P2 EXECUTE source candidate — source/unit preflight, not runtime acceptance

The preceding codec candidate0ceca7cd597c7c8f69c85d3898a407ee7c954441 passed all
five jobs in [CI39548803322](https://github.com/masahitojp/mariamem/actions/runs/39548803322).
Its saved both-OS runtime records still explicitly cover **P1 only**; they do not
certify the newly added EXECUTE owner described here.

The current authored source now connects host EXECUTE to opcode5 and public
mysql_stmt_bind_param/execute/bind_result/store_result/fetch/fetch_column. It is
an intermediate candidate, not an accepted implementation or product claim:

- The host resolves session-owned IDs/generations and expands cached descriptors
  into exact values. Invalid packets cannot update that cache or reach the
  engine. SQL errors preserve native errno/state; successful typed results must
  name the owning native handle and match the current metadata/row widths.
- C independently checks typed counts, types, padding, flags and byte ranges.
  Parameter buffers are aligned and privately owned until a successful rebind
  or native close; no request buffer survives by reference. Native handles are
  destroyed before freeing pointers after a partial API bind failure. Such a
  failure terminates transport rather than fabricating success.
- MYSQL_TIME receives explicit components. Its native buffer length is
  sizeof(MYSQL_TIME), **not** the protocol body's0/4/7/8/11/12-byte length:
  pinned sql_prepare.cc:1188–1257 passes *MYSQL_BIND.length to the embedded
  converter, whose temporal handlers require the native structure size. Fixed
  numeric values use exact-width aligned buffers and typed bit copies.
- Each execution obtains current result metadata and typed numeric/temporal
  buffers. Variable fields first use a one-byte scratch buffer, then their
  reported complete length drives fetch_column; NULL, truncation/error and
  returned length are checked. The scratch size is not a cell capacity. A
  serialized-envelope overflow fails closed rather than returning shortened data.
- Results carry an explicit binary_rows discriminator and exact hex bytes. The
  host uses the tested binary-row encoder and PREPARE-compatible metadata flag
  normalization. DML counts/insert IDs remain decimal uint64 strings until wire
  encoding. Text/authentication, opcode4 and public APIs remain unchanged.

[Local evidence](v06x-prepared-execute-evidence/receipt.json) records ordinary
C plus ASan/UBSan and related Go packages with race, all PASS. The C harness adds
typed-buffer ownership/copy/alignment,65 bindings, full8,194-byte retrieval,
malformed lengths/counts, SQL error/recovery, partial bind failures and cleanup.
Host tests compare complete rows/metadata to saved native vectors, reject invalid
typed envelopes and preserve uint64 DML values above2^53. **These are mocked C
APIs and Go components using the old canonical runtime, not new-guest execution.**
See [reproduction and remaining work](v06x-prepared-execute-evidence/reproduce.md).

The dedicated branch's CI schedules the fixed-source build and both-OS unit jobs
only. The development-runtime job is explicitly **SKIP pending exact new-guest
binding review**, not PASS or waived acceptance. The normal prepared-product
branch still requires that complete job. Old P1-only Wasm/function/data pins are
unchanged and reject unknown inputs. No matching-by-relocation or second allowed
guest is introduced; generated Go is not edited. After the source output is
available, review its exact functions/data and install the binding before
running the real P2 probe against the unchanged native reference.

P2 remains incomplete: actual guest execution, extended temporal/SQL-mode cases,
DML/warnings and schema/reprepare, and named field forms need native comparison.
Unusual wire parameter types and the public API's accepted binding types still
need explicit reconciliation; sharing a result byte shape is not proof of that
mapping. Prepared result chains are P3: PS_MULTI_RESULTS remains unadvertised,
and unexpected MORE_RESULTS in this intermediate owner fails the transport
rather than silently dropping a result. LONG_DATA remains P4. Canonical and full
J1/P6 generation checks and consumers/regressions are not closed by the source
preflight. The C-extension syntax-error disposition is recorded separately as
native parity (see the decision section) and does not close runtime acceptance.
No scope is removed.

P1 CI at3eda067
([39537687879](https://github.com/masahitojp/mariamem/actions/runs/39537687879))
passed source/unit jobs, the repaired development SQL/transaction/Snapshot/Fork/
Close smoke and the exact installed binding checks (including7 mutation tests)
on both OSes. The real wire probe completed its six lifecycle/error/ownership
checks but failed the final comparison to native metadata. Its overall FAIL is
preserved in the [metadata-fix evidence](v06x-prepared-p1-metadata-fix/receipt.json).
The two platforms' captured failure records are byte-identical.

The cause is a representation difference the host failed to translate:
pinned libmysqld/lib_sql.cc copies server_field.flags into MYSQL_FIELD, then adds
NUM_FLAG(0x8000) for the include/mysql.h IS_NUM types; protocol.cc serializes the
original server flags. PREPARE column serialization copied that augmented C API
value verbatim. The source receipt pins exact files/lines. This is not evidence
of SQL data corruption; it is an observable metadata mismatch.

The repair is in the handwritten host serializer only: undo that C-derived bit
for exactly the pinned IS_NUM type set, preserving every other bit and all flags
for non-IS_NUM types. NULL6 belongs to that C macro, while TIMESTAMP7 and BIT16
do not. No C overlay, Wasm, converter, generated Go, native reference fixture or
comparison oracle is changed. A race-enabled standalone test of the production
flag owner checks all256 type IDs and replays140 captured descriptors against
the unchanged native packets; exactly68 numeric descriptors change. Every byte,
including names, charset, widths, decimals and other flags, must then match.
At the repair's submission, this replay passed locally; full-package tests and
corrected actual wire behavior remained for exact-source CI. The corrected
gate above subsequently passed; this historical FAIL is not relabelled.

The historical text serializer also forwards the C API flags. It is unchanged
here; native text-column comparison belongs in the already planned P5 metadata/
text regression before deciding that existing boundary. This repair adds no
claim of complete text metadata parity or complete P2–P6 acceptance.

P1 development CI at e9fe604
([39434643324](https://github.com/masahitojp/mariamem/actions/runs/39434643324))
failed in the common smoke after generation/compilation on both native targets.
Source compilation and both unit jobs passed. Ubuntu reached Snapshot before
the just-closed SQL connection's server cleanup finished; macOS completed the SQL/
Snapshot/Fork portion, then failed an obsolete Database._process assertion from
the pre-shared-host model. Binding and prepared wire probes were skipped, so no
P1 runtime PASS follows. The [failure receipt and excerpts](v06x-prepared-p1-smoke-fix/receipt.json)
retain this result; excerpt paths are scrubbed as recorded by their original and
stored checksums.

The repair changes only the development smoke: use the supported
wait_disconnected before Snapshot, require children to share their lineage's
session, keep the host alive while the baseline owns it, then require all DBs/
owned logs disposed and the last shared host reaped with closed pipes/stderr,
stopped reader and removed scratch. Runtime code, Busy/transaction guards and
failure oracles are unchanged. Existing shared-host ownership and dev-tool tests
passed52 cases locally; the actual guest smoke and later P1 probes require the
new exact-source CI. No exception or incomplete unit is accepted by this repair.

| Unit | State and next evidence |
| --- | --- |
| P1 | Corrected development gate at3496095 PASS on both OSes, including actual ownership and native metadata comparison; later full-scope acceptance remains required |
| P2 | TIME-repaired actual22-case EXECUTE and13-case TIME/native gate PASS on both OSes atf498396; extended DML/warnings/schema-reprepare/type/SQL-mode coverage pending |
| P3 | Prepared CALL/results/OUT and later-error draining pending |
| P4 | LONG_DATA/no-response/reset/pool/cancel/disconnect and failure/resource matrix pending |
| P5 | Real Go/Python prepared consumers, native controls and both-OS regression pending |
| P6 | Canonical new source builds, independent generation, strict J1 rebind, licenses/provenance/inventories and guards pending |

The [P1 workflow](../../.github/workflows/prepared-product.yml) runs source/units
and the new development runtime gate described above. It intentionally does not
run Qualification or relabel the old canonical runtime as this new guest.
Continue the authorized units after this gate; do not ask for a new implementation
approval merely because a stage ended.

The canonical guest and release ledger remain the main routine baseline. A normal
canonical source build must continue to reject newly changed Wasm until P6's
explicit adoption inputs/provenance are prepared. A green P1 source/unit run
cannot complete P1–P6, authorize main integration or replace the recorded
C-extension native-parity disposition. Final Human Review follows the whole approved scope or a concrete
blocking finding; no release/version/public API change is made here.

## Human decision — C-extension syntax error accepted as native parity

2026-10-21. The Human decided to match native MariaDB rather than treat this as a
mariamem defect or block prepared adoption. The guest already matches native;
the old oracle expectation, not the server behavior, was the mismatch.

| Layer | PREPARE syntax-error result |
| --- | --- |
| Server raw wire | 1064 / 42000 |
| Connector/Python 26.7.0 pure | 1064 |
| Connector/Python 26.7.0 C extension | 2006 / HY000 (`MySQL server has gone away`) |
| Native MariaDB 12.3.3 + the same C extension | 2006 |

This is a consumer error-presentation difference on the prepared syntax-error
path, not a server or guest regression. It affects no successful prepared
execution.

Required disposition:

- Split the oracle: server raw wire **1064/42000**; pure Python **1064**;
  C extension **2006/HY000** as the native-parity expectation.
- Keep the original C-extension 1064 attempt as a historical **FAIL**. Do not
  relabel it PASS, fabricate 2006 on the server, or advertise exact exception-code
  parity for the C extension.
- Acceptance conditions: fresh raw-wire evidence still shows 1064/42000; the same
  pinned native consumer produces 2006; both connections remain usable afterwards
  (a following text SELECT/PING succeeds).
- Do not force pure mode, use interpolation, or weaken J1/truncation/wrong-error/
  ownership oracles to make the split pass.
- Document the C-extension behavior when prepared support is published; revisit
  the disposition if a future connector/native version changes it.

This records the adoption disposition. It is not a new implementation approval
and does not convert any pending runtime unit into PASS.

## P4 source note retained for the next implementation unit

Pinned83e909fc libmysqld/libmysql.c (SHA256
`d8f0a9d4f7c638bd91d11453e1207ccfe6d3cda85f9c3082e51c37a69c9fc60c`)
shows mysql_stmt_send_long_data checks the currently bound type (lines3003–3046),
while mysql_stmt_bind_param clears client long_data_used flags (line2867).
Therefore forwarding an initial LONG_DATA before any binding is not established
by source alone; preserve the engine-owned accumulation goal, verify the public
API binding/order path in the actual guest/native controls, and do not claim it
implemented. No new LONG_DATA result or blocker conclusion is inferred here.

P1 wire-integration note: current Serve can reopen its MYSQL for FOUND_ROWS after
reading the initial greeting identity. Capture the prepared schema/operations and
session generation from the final successful open, not the earlier overwritten
query result; initialize the statement registry only for that final session.
Include flagged and unflagged connections in the P1/P5 integration cases.

## P2 exact binding continuation after source preflight

[CI39554451701](https://github.com/masahitojp/mariamem/actions/runs/39554451701)
at source_commit00962f85fff7cdddadf8724c05f0f44834197b79 passed source compilation
and both-OS units; development runtime jobs were intentionally skipped.
Its18,400,359-byte guest has SHA256
`a52dd707d337d5349a7c5d72bc2108dc823cfe0c625742e93bc0875a2e3b519a`.
The [binding receipt](v06x-prepared-p2-binding-evidence/receipt.json) and
[reproduction steps](v06x-prepared-p2-binding-evidence/reproduce.md) bind the fixed
source/toolchain, converter13 patches, raw generation and source-adapter outputs.

Fn131 is unchanged. Fn153 and Fn214 differ only in observed absolute-address
literals, each increased by1152; the complete normalized bodies otherwise match
the P1 preimages. This is an offline comparison, not a relocation-tolerant guard:
installation still requires exact complete hashes, and fresh address mutations
are rejected. TLS505 bytes match exactly. Other initial data differs; its exact
hashes/ranges are pinned without claiming full semantic equality from numeric
relocations. The canonical generated tree is unchanged. No generated Go was
hand-edited, converter patch changed, or unknown guest admitted by a fallback.

Formal raw translation verification and source-only adaptation passed. The atomic,
MemFS and lifetime owner transformations passed in their formal adapter order;
50 local input/mock/sanitizer/binding checks passed. These are not execution of
the new guest, a full J1 failure/control run, or independent source regeneration.
The next prepared-product push rebuilds the guest at the submitted commit and
runs formal development generation/compile/smoke, exact installed bindings,
P1 lifecycle/native metadata and P2 typed EXECUTE/native binary vectors on both
OSes. P2's remaining temporal/DML/schema/type matrix and P3–P6 remain open. The
C-extension syntax-error disposition is recorded as native parity (see the
decision section); it does not close runtime acceptance. No main adoption or
release is requested or performed.

## P2 development gate: mutation-test targeting repair

[39561037019](https://github.com/masahitojp/mariamem/actions/runs/39561037019)
at source_commit6a9a84290ecd6d31d51cc21109a0c49f660f9314 passed source, both-OS
units, formal generation/compilation/SQL smoke and the exact installed P2 binding
checker. Both runtime jobs then failed one of10 mutation tests; P1/P2 actual wire
probes were skipped. This is not a completed P2 runtime comparison.

The new address-mutation test used file-wide first replacement. In an installed
part file, the same address appeared before Fn214, so it changed an unrelated
function, left Fn214 intact and incorrectly expected the exact Fn214 guard to
reject it. Local units had used the isolated reviewed Fn214 fixture, hiding that
context dependency. The repair extracts the named body first, changes the literal
inside that body, verifies the changed body is present, then checks rejection.
The regression includes a preceding unrelated function containing the same literal
for both tested targets. Local replay confirms the old mutation misses the target
and the corrected mutation is rejected; all12 focused binding tests pass.

[Receipt, original both-OS failure logs and local transcript](v06x-prepared-p2-mutation-fix/receipt.json)
preserve the failure. Runtime/guest/converter/source-origin policy, exact hashes,
preimages and native comparison fixtures are unchanged. Only the test and progress
evidence change. Resubmit the existing complete development workflow; no canonical
regeneration, main integration, Qualification or publication occurs here.

## P2 actual native comparison: TIME metadata decision

The corrected gate atab5c39d ([39565377640](https://github.com/masahitojp/mariamem/actions/runs/39565377640))
passes source/units, development smoke, exact bindings, all12 mutation tests and
actual P1 comparison on both OSes. P2 executes22 cases and fails the unchanged
native comparison: negative fractional >24h TIME has declared column length16
instead of23. All other captured descriptor fields, binary rows and terminal
packets match. This is a real metadata discrepancy, not a repeated mutation-test
failure or observed SQL data corruption.

The [Human decision and one-line proposal](v06x-prepared-p2-time-metadata.md)
record the pinned embedded/ordinary Item_param source asymmetry, exact captures,
limited next implementation/verification and cost. The design requires stopping
before a MariaDB-internal edit; no source patch or further CI run is submitted.
P2–P6 remain unfinished and the original oracle/expected fixture is unchanged.

## P2 TIME repair — approved bounded implementation started

After upstream-history review and correction, the Human approved the bounded
MariaDB-internal change. [Source-stage evidence](v06x-prepared-p2-time-repair/receipt.json)
records the single experimental line change and complete before/after hashes.
The preparation owner rejects changed full source/patch/postimage and repeated
application; it records the experimental input separately.61 focused checks pass.
The fixed native container passes13 extra TIME controls and the unchanged22-case
oracle. Guest/manifest handling is explicitly experimental; release rejection and
canonical source.patch/converter13 patches remain unchanged.

A source/unit preflight produces the new Wasm. Development runtime is intentionally
skipped until its exact identity and function/data/TLS binding are reviewed.
The full prepared-product gate now includes the additional TIME/native comparison
alongside existing P1/P2 probes. No patched guest runtime PASS, completed P2-P6,
main adoption, Qualification or release follows from the native/local checks.

## P2 TIME repair — exact binding reviewed, full development gate next

[Source preflight39572844101](https://github.com/masahitojp/mariamem/actions/runs/39572844101)
at source_commit4f41be87ac30c86cf688b150afb5493fed6b6a1b passed source compilation
and both-OS units. Development runtime was intentionally SKIP until binding review.
The new18,400,359-byte Wasm has SHA256
`3bfb1030a0588aa0d8f64b7bcd0a220d0eae8f95a181b8e1ff5f99eaffa320a8`.
[Receipt](v06x-prepared-p2-time-binding/receipt.json) and
[reproduction steps](v06x-prepared-p2-time-binding/reproduce.md) bind the source,
experimental patch, toolchain and formal raw/source-adapter generation.

The fixed converter binary and all13 patches match the previous P2 translation.
Only raw p7/p7_pure.go differs; every other raw inventory file matches, with no
added/removed files. All three allocation/lifetime function hashes and reviewed
fixtures, the full data.bin/ranges/constructors and505-byte TLS match exactly.
The single accepted guest SHA changes; no function preimage hash or generated Go
is hand-edited. Rejection now explicitly includes the immediately previous P2
Wasm as well as P1 and canonical baseline identities.62 focused input/mock/
sanitizer/binding/patch checks pass locally. Formal source-only adaptation and
pure installation owners pass; no full local runtime installation is claimed.

Submit the complete prepared-product development gate at the new exact source:
fresh source build, generation/compile/SQL smoke, exact installed bindings and
mutations, actual P1/P2 comparison and the extra13 TIME cases. Passing the source
preflight/rebind is not passing those guest comparisons or completing P2–P6.
Canonical source.patch, converter and native expected packets remain unchanged.
No main adoption, Qualification or publication is performed.

## P2 TIME repair — actual both-OS verification PASS

[CI39577305621](https://github.com/masahitojp/mariamem/actions/runs/39577305621)
at source_commitf498396d2547070a80e5a8d758f5eaada670d145 passed all5 jobs.
[Result receipt and captured TIME/binding outputs](v06x-prepared-p2-time-result/receipt.json)
confirm actual original22 P2 cases and13 additional TIME cases match the complete
unchanged native packets on macOS arm64 and Ubuntu x86_64. The original16-vs23
TIME descriptor discrepancy is resolved for the reproducer. P1 actual lifecycle/
native metadata, development SQL/transaction/Snapshot/Fork/Close smoke and13
binding checks per platform also pass. Both artifacts bind the exact candidate
and guest3bfb1030a0588aa0d8f64b7bcd0a220d0eae8f95a181b8e1ff5f99eaffa320a8.

All generated-inventory entries except provenance.json match across platforms.
The native converter binaries differ by platform; provenance binds development
input manifests. The receipt records these identities separately and does not
claim complete provenance equality or independent Wasm source generation.

This closes the bounded TIME repair/matrix, not P2–P6. Extended DML/warnings,
schema/reprepare, additional wire/public-API type reconciliation and SQL modes
remain P2 work; P3–P6 are unchanged. No acceptance condition/oracle was reduced,
no source patch became canonical, and no main adoption/Qualification/release is
implied. This evidence-only follow-up does not rebuild unchanged runtime code or
re-trigger the same development CI.

## P2 additional20-case matrix — next actual guest gate

After the TIME repair, [additional P2 controls](v06x-prepared-p2-matrix.md) cover
DML/uint64 IDs/counts, warnings and recovery, commit/rollback, DATE SQL modes,
wire/public-API type handling and engine schema reprepare. All20 independent
scenarios pass the fixed native engine;4 local packet/oracle controls pass.
[Receipt](v06x-prepared-p2-matrix-evidence/receipt.json) records exact inputs and
scope. Actual guest acceptance is pending. Failures keep partial responses and
a following-query health observation, while later scenarios continue independently.
The guest, converter, single binding and original P1/P2/TIME oracles are unchanged.
The full development gate now adds this comparison after the existing probes;
no new canonical inputs, main adoption, Qualification or release is attempted.

## P2 matrix failure — isolate DB termination before judging later scenarios

[39582653522](https://github.com/masahitojp/mariamem/actions/runs/39582653522)
at007b323 passed the source/unit/previous runtime gates on both OSes. The new
matrix matched DECIMAL/VARCHAR, then BIT EXECUTE timed out and the shared DB
terminated. All17 later scenarios failed to connect to that dead DB. The18
reported differences are not18 separately established implementation defects.
[Failure receipt](v06x-prepared-p2-isolation-evidence/receipt.json) preserves the
identical both-OS capture. The harness repair creates an independent root DB/host
per guest scenario, captures logs before/after close and retains lifecycle errors.
Six local controls pass. Native packets/scenario functions/oracles remain intact;
the BIT implementation is not repaired and no new guest identity is introduced.
Repeat all20 cases on both OSes to establish the actual repair scope. A green
result is not assumed; source-internal edits still require the existing decision.

## P2 isolated matrix — eight actual failures, additional repair decision

[CI39585983268](https://github.com/masahitojp/mariamem/actions/runs/39585983268)
atd11f4ff completes all20 in independent DB/hosts on both platforms:12 match
native, seven parameter type inputs independently time out, and schema-add
returns2057 followed by commands-out-of-sync2014. Earlier gates still pass.
[Current failure assessment](v06x-prepared-p2-blockers.md) records source owners,
exact evidence and the proposed bounded continuation. No implementation repair
or new source change is included. The existing MariaDB-internal stop condition
now requires a Human decision before expanding the patch scope. P2 remains open;
neither harness isolation nor the12 passing scenarios completes P2–P6.

## P2 bounded repair continuation — approved source candidate

The Human approved proceeding with the two-part proposal.
[Candidate and reproduction](v06x-prepared-p2-repair.md) record the WASIX embedded
raw-type binding extension, single-execution metadata rebuild, allocation/error
cleanup, exact combined patch ownership and15 additional native controls.
All91 focused local tests pass, including pre-fix source controls, sanitizers,
metadata allocation failure injection and duplicate-execution oracle rejection.
Native15/20/22/TIME13 replay and unchanged canonical inventory/public checks PASS.
These are components/reference checks, not actual patched guest execution.
Submit source/unit preflight on experiment/prepared-p2-repair; only after the
new guest identity/body/data/TLS review should the full prepared-product gate
run. The eight guest failures remain unclosed until that comparison passes.

## P2 repair guest — exact binding reviewed, actual both-OS gate next

[Source preflight39596726209](https://github.com/masahitojp/mariamem/actions/runs/39596726209)
passes guest-source and both-OS units at68fb5c2. Guest41ab4076 is verified against
the exact clean source inventory and unchanged toolchain; the fixed converter
and13 patches reproduce byte-identical Fn153/Fn131/Fn214, full data and TLS.
[Binding evidence/reproduction](v06x-prepared-p2-repair-binding/reproduce.md)
preserve the complete raw inventory, including30 changed files of51. Formal
source adapter/pure owner transforms and94 local checks pass. Memory initialization
placements are explicitly checked and the complete Fn67 body is added to the
installed checker with an offset mutation rejection test. Only the new guest
identity is accepted; four older identities are rejected, not allowlisted.
Submit full prepared-product CI for installed bindings, smoke and all existing
plus15 repair native controls. Actual runtime PASS is pending; no generated Go
edit, canonical regeneration completion, main merge or release is claimed.

## P2 actual repair gate — unsigned NULL flag mismatch remains

[CI39601636017](https://github.com/masahitojp/mariamem/actions/runs/39601636017)
ate8f5f76 passes smoke/installed bindings/P1/22/TIME13/additional20 on both OSes.
The added15-case gate has seven mismatches: initial/reused unsigned NULL column
flags omit0x20; rows/terminals and following SQL match throughout. All other
cases, including single-execution grow/shrink, match native. P2 is not complete.
[Parameter-order repair](v06x-prepared-param-order.md) addresses the current
descriptor before conversion in both embedded execution paths. Local102 checks,
exact full-source application and unchanged15/extra2 native replay PASS.
No expected fixture or guard is weakened. Submit source preflight on
experiment/prepared-param-order, review its new identity before the actual gate,
and retain all prior oracles. This is inside the approved bounded input repair;
no main adoption, version placement, Qualification or release is decided.

### Parameter-order guest binding continuation

Source preflight39607505031 passes guest-source and both-OS units at a342f30.
New guest4dad84d0 is reviewed against the unchanged converter/13 patches,
all lifetime function bodies, full data/TLS and complete memory initialization.
The single binding advances; the immediately previous41ab4076 is additionally
rejected. Local103 focused checks PASS. See the [binding receipt](v06x-prepared-param-order-binding/reproduce.md).
Actual both-OS unsigned/NULL native comparisons remain pending; no P2 completion,
main adoption or release judgment is implied.

### P3 source preflight supplied by the Human

The [embedded CALL/OUT source review](v06x-prepared-p3-source.md) confirms the
public next-result API, exact embedded methods slot, internal capability path
and upstream test/build target at the fixed MariaDB commit. The embedded connect
path itself adds CLIENT_CAPABILITIES; this is distinct from the external wire
capability, which remains unadvertised during P2. Actual P3 execution is NOT RUN.
First exercise one OUT plus two ordinary results and complete native sequence/
following SELECT1 within P3, then retain the full approved matrix. No P2 gate,
prepared scope, generated source or release boundary changes here.

### P2 specified development row closed at5146d8a

[CI39616628715](https://github.com/masahitojp/mariamem/actions/runs/39616628715)
passes all five jobs, including both native-platform runtime gates. Each OS
passes P1, installed binding/17 mutations, SQL/transaction/Snapshot/Fork/Close
smoke and22+13+20+15+2 typed/native scenarios. The former unsigned/NULL metadata
failures no longer reproduce. [Current disposition and saved evidence](v06x-prepared-p2-pass.md)
map these results to every specified P2 development criterion, superseding the
pending P2 states above without rewriting their historical evidence. P3–P6,
production adoption and release remain open; continue with the minimal P3 CALL
case before its full matrix. No runtime source is changed by this evidence entry.

### P3 first CALL source candidate

The [minimal candidate](v06x-prepared-call-minimal.md) adds guest-side typed
result capture/next-result handling and Go EXECUTE-only ordered binary chains.
The fixed native case (two ordinary results, OUT and terminal OK, followed by
SELECT1 and CLOSE/PING) passes capture/replay. Local106 Python/C checks and three Go race packages PASS; they cover metadata/
buffer switching, status retention, malformed-chain rejection and later errors.
Actual new guest generation, exact binding and both-OS execution remain pending;
old binding guards reject unknown Wasm. External PS_MULTI_RESULTS stays
unadvertised until full P3 acceptance; no public API/converter/canonical patch or
Generated Go is changed. Source preflight and P3 actual runtime are separate.

### P3 source preflight and exact new guest binding

[Preflight39624071363](https://github.com/masahitojp/mariamem/actions/runs/39624071363)
passes guest-source and both-OS units at46f5c2c; runtime is SKIP by branch design.
The [binding review](v06x-prepared-call-binding/reproduce.md) binds gueste6d6021a
through unchanged converter13 patches. It explains all64-byte BSS reference shifts,
full data/segment/init identities and unchanged505-byte TLS, then pins complete
preimages without numeric normalization. Local107 checks PASS and all older
guests remain rejected. Formal installation/compilation and actual P1/P2/minimal
CALL comparison on both OSes remain the next prepared-product CI gate. P3 actual
acceptance and full P3–P6 are not closed by source/layout/component evidence.

### P3 minimal real-guest/native gate PASS at42be2b5

[CI39631360824](https://github.com/masahitojp/mariamem/actions/runs/39631360824)
passes all five jobs. On both OSes the minimal CALL produces both ordinary
results, OUT with SERVER_PS_OUT_PARAMS, terminal OK and healthy following
SELECT1/CLOSE/PING, matching complete native metadata/packet bytes/status.
P1/all72 P2 cases, smoke and18 installed binding mutations also PASS. See the
[saved results and remaining scope](v06x-prepared-call-pass.md). This closes only
the first P3 feasibility gate; full P3/capability truthfulness, P4–P6 and later
production/release decisions remain open. No runtime code changes here.

### Full P3 local matrix and bounded negotiation repair

[Source/evidence](v06x-prepared-p3-matrix.md) preserves13 native controls and
baseline11 PASS/2 FAIL: dedicated OUT results were emitted without external
PS_MULTI_RESULTS negotiation. The Go-only repair validates the complete guest
chain before native-matched OUT selection; normal results/errors are retained.
Ready/open is checked before conditional EXECUTE capability advertisement;
FOUND_ROWS still replaces the registry and binds final client flags.
A paired positive control adds one case without changing any prior expectation.
The source49cb504 handwritten host and unchanged99-file guest runtime pass all14
actual/native cases on macOS, prior P1/all72 P2, minimal CALL and SQL/transaction/
Snapshot/Fork/Close smoke. Local112 Python/C and3 non-race Go packages PASS.
The diagnostic composite source/binary receipt is distinct from the unchanged
formal baseline record. Fresh both-OS candidate/race CI remains required; no
source-origin guard, generated Go, guest or converter changes are introduced.
P3 is not closed locally, and P4–P6/main/release decisions remain open.


### Full P3 development acceptance PASS on both OSes

[CI39686154515](https://github.com/masahitojp/mariamem/actions/runs/39686154515)
at6fc594a freshly generates/compiles the candidate and passes all14 P3 native
comparisons, truthful advertisement and negotiated on/off behavior on macOS arm64
and Ubuntu x86_64. All following QUERY/CLOSE/PING and per-case cleanup controls
PASS, as do prior P1/all72 P2, minimal CALL, smoke,112 Python/C checks, three Go
race packages and18 installed mutations per OS. [Saved acceptance evidence](v06x-prepared-p3-pass.md)
closes the approved P3 development row. P4 lifetime/resources/long data, P5 consumer
regressions and P6 canonical/J1/independent generation remain unfinished. No main
integration, Qualification or release decision is implied.


### P4 first lifetime slice and lifecycle packet boundary repair

The [candidate and remaining P4 scope](v06x-prepared-p4-lifetime.md) add seven
native-controlled lifetime scenarios, including pinned Go DB/Tx/Conn/pool usage,
RESET/type/transaction lifetime, engine quota recovery and idle QUIT/EOF cleanup.
Native capture/replay PASS7/7. Short/surplus CLOSE/RESET bodies revealed a bounded
host/native mismatch: decode their ID in a zero-filled4-byte local header rather
than terminating CLOSE or returning RESET1835. No guest/converter/generated or
binding identity changes. Local114 Python/C checks and three Go race packages
PASS; prepared-product CI now requires the actual-guest matrix on both OSes.
P4 remains unfinished: LONG_DATA, prepared executing-query failure/cancellation
and the complete resource/failure matrix are not waived by this first slice.


### P4 first lifetime slice PASS on both OSes at ecfea4a

[CI39699613828](https://github.com/masahitojp/mariamem/actions/runs/39699613828)
passes all five jobs at source_commit ecfea4ab6b1e9b665a89ac000c655fb584bfd754.
[Both-OS evidence](v06x-prepared-p4-lifetime-evidence/ci/receipt.json) confirms all7
P4 lifetime scenarios/native comparisons, including Go DB/Tx/Conn/pool usage,
RESET/transaction/type reuse, malformed lifecycle adjacency, native quota recovery
and idle QUIT/EOF cleanup. Every case restores active connections to0 and removes
temporary state; the Go consumer restores native statement counts/open connections
to0. Previous P1/all72 P2/all14 P3/minimal CALL, formal generation/compile/smoke,
114 Python/C checks, three Go race packages and18 installed mutations also PASS
per OS. This closes this lifetime slice only. LONG_DATA, prepared executing-query
cancellation/disconnect and the remaining resource/failure matrix keep P4 open.
Guest/converter/canonical generated ownership is unchanged; main adoption,
Qualification and release remain separate decisions.


### P4 LONG_DATA source candidate and native25 controls

[Candidate and evidence](v06x-prepared-long-data.md) implement engine-owned chunks
through public mysql_stmt_send_long_data, typed omission/NULL precedence, bounded
presence maps, deferred1210 and RESET/CLOSE cleanup. Native25 capture/replay PASS,
including accepted/rejected types,65 parameters,1MiB aggregate crossing and native
capacity1105/repeated error/reset. Local118 Python/C checks and3 Go race packages
PASS. The authored type guard uses public RESET before SQL; diagnostic command
counts are not exact network parity. Canonical/experimental upstream patches and
converter13 patches remain unchanged. New guest source-build CI and exact full
binding review are required before actual runtime acceptance; old e6d6021a pins
remain unchanged and fail closed. The eventual prepared-product gate requires
all old P1/P2/P3/P4-lifetime controls plus the25 new cases on both OSes. LONG_DATA
and P4 remain incomplete until that gate and remaining cancellation/resource
work close; no main adoption, Qualification or release is implied.

### P4 LONG_DATA exact binding continuation

[Source39714836816 and binding evidence](v06x-prepared-long-data-binding/reproduce.md)
verify guest f5ce001d from425c821 with unchanged fixed converter13 patches.
Lifetime functions/init/TLS are identical to P3; data and single-guest identity
are repinned with old-P3 rejection. Both-OS actual runtime acceptance is next,
not yet PASS. Full P4 and P5/P6 remain unfinished.

### LONG_DATA strict metadata gate failure

[CI39718930329 analysis and source repair](v06x-prepared-param-metadata.md):
both-OS prior runtime gates PASS; LONG_DATA strict comparison FAIL despite all25
individual assertions passing. Replace the generic parameter descriptor with
engine-owned metadata rather than relaxing aliases in the native oracle.
The source-repair branch must rebuild before another exact binding/runtime gate.

### Parameter metadata source PASS and new binding

[CI39724676227 and binding](v06x-prepared-param-metadata-binding/reproduce.md)
confirm embedded C++ compilation at ab8c350 and exact new guest8f617762.
The complete reviewed functions/init track BSS+64 with unchanged TLS; old
f5ce001d is rejected. Local122 checks PASS. Strict both-OS runtime/native parity
is next and remains unconfirmed; P4/P5/P6 are not closed.

## Both-OS LONG_DATA/native metadata development gate closed

[CI39729456821 at fba09f6](v06x-prepared-long-data-pass.md) passes all25
LONG_DATA/native comparisons including the previously wrong parameter names,
plus the previous runtime gates and cleanup controls on both OSes. No oracle
or native fixture was weakened. Full P4 (active-query cancellation/disconnect
and remaining failure/resource paths), P5/P6 and adoption remain unfinished.

## P4 active EXECUTE exit candidate

[Candidate and bounded matrix](v06x-prepared-p4-active.md) uses a SQL execution
witness before client cancellation, deadlines, EOF/reset and DB.Close. Native5
controls PASS; actual guest7-case and both-OS acceptance remain pending. A small
shared-control classification repair restores unusable for invalidated-DB status
without changing ordinary request timeout behavior. Guest/converter/binding
identities and prior gates remain unchanged. Full P4/P5/P6 remain unfinished.

### P4 active exits PASS on both OSes at fbe4196

[CI39747013913](https://github.com/masahitojp/mariamem/actions/runs/39747013913)
passes all five jobs. The [active-exit report and receipt](v06x-prepared-p4-active.md)
record all7 real guest cases, witnessed active execution, target disposition,
healthy siblings/baseline reuse and final cleanup. Prior matrices,134 Python/C
checks,4 Go race packages and20 binding mutations PASS per OS. Guest/converter/
generated source inputs remain unchanged. Remaining failure/resource paths keep
P4 open; P5/P6, adoption, Qualification and release are separate.

### P4 failure/resource closure candidate

[Finite ledger, exact scope and local evidence](v06x-prepared-p4-failures.md)
add fail-at-N owner allocation and serializer checks, truncated-refetch negatives
and full-dispatcher no-partial-result/state-preservation controls. Local macOS134
Python/C checks and4 Go race packages PASS; two isolated negative mutations fail
as expected. Both-OS component CI is pending. Runtime/guest/converter inputs are
unchanged, so no new actual guest PASS is claimed. This is a P4 closure candidate
against the existing approved row, not P5/P6, adoption or Qualification completion.
