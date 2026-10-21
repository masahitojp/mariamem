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
wire/native differential probe on macOS arm64 and Ubuntu x86_64. Results remain
pending until that CI completes. It is not Qualification, full P1–P6 acceptance,
or main-adoption approval.

## Remaining authorized work

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
| P1 | Source CI/both-OS units and expanded native control PASS; host lifecycle dispatch added; new-guest/native metadata and actual ownership acceptance pending development CI |
| P2 | Typed EXECUTE/binary/temporal/large-value implementation pending |
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
cannot complete P1–P6, authorize main integration or accept the C-extension error
exception. Final Human Review follows the whole approved scope or a concrete
blocking finding; no release/version/public API change is made here.

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
