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
