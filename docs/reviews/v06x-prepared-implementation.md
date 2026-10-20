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
- Host PREPARE metadata serializer and schema/identity validation are added as
  components. **They are not yet wired into public command dispatch.** The main
  unsupported-PREPARE test is retained until full execution is implemented.
- An internal typed-envelope overhead allowance preserves the full1MiB SQL input
  while normal text request limits remain unchanged. Public packet limits are
  not raised. No generated Go is hand-edited or repinned in this stage.

## Verification and explicit limits

| Evidence | Local result | What it does not establish |
| --- | --- | --- |
| C ownership/failure harness, ordinary + ASAN/UBSAN | PASS | Mock public API, not embedded engine semantics or new guest execution |
| >64 handles/parameters/columns; generation/closed handle negatives; prepare/metadata/allocation/late response-failure unwind | PASS in the harness | No capacity/performance promise and no proof of actual native metadata equivalence |
| Go preparedproto registry/envelopes with race | PASS | Serial per-session registry is not a concurrent map API |
| Host PREPARE metadata/error/malformed-response tests with race | PASS | Pinned generic descriptor still needs the expanded actual guest/native matrix |
| Guest request budget tests and existing package tests with race | PASS | Tests compile/run against the current checked-in canonical guest, not the new C overlay |
| Helper/source/J1 input tests plus C harness |46 PASS | Existing J1 checks remain bound to the old canonical artifact; new guest binding is pending |
| New guest source compilation | Pending source CI | Single development build is UNQUALIFIED; never independent same-input source reproduction |

[Local receipt](v06x-prepared-p1-evidence/receipt.json) binds tested owner/test
hashes, actual tool versions and the four saved unit transcripts.

No existing failure oracle is weakened. Native compile success will establish
actual header/link availability, not completed P1 runtime semantics. The new C
owner's native MariaDB behavior, expanded parameter descriptors, actual worker
isolation, fresh guest identity/layout and end-to-end wire PREPARE still need
verification. P1 is therefore **partial**, not complete.

## Remaining authorized work

| Unit | State and next evidence |
| --- | --- |
| P1 | Source/components/unit checks present; actual new-guest/native metadata and integrated ownership acceptance pending |
| P2 | Typed EXECUTE/binary/temporal/large-value implementation pending |
| P3 | Prepared CALL/results/OUT and later-error draining pending |
| P4 | LONG_DATA/no-response/reset/pool/cancel/disconnect and failure/resource matrix pending |
| P5 | Real Go/Python prepared consumers, native controls and both-OS regression pending |
| P6 | Canonical new source builds, independent generation, strict J1 rebind, licenses/provenance/inventories and guards pending |

The [P1 workflow](../../.github/workflows/prepared-product.yml) runs both-OS unit
checks and compiles a single fresh development guest using the formal source
preparation recipe. It intentionally does not run Qualification or relabel the
old generated runtime as this new guest. After source CI, consume its actual
artifact identity and continue the authorized units; do not ask for a new
implementation approval merely because a stage ended.

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
