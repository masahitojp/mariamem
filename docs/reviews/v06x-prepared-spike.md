# Prepared bridge spike — Human Review

2026-10-19. Decision now: whether to proceed to production implementation of the
guest `mysql_stmt_*` bridge and host binary protocol. **Recommend proceeding to
production design/implementation, with the gaps below as acceptance conditions.**
The public embedded API worked in the real MariaDB 12.3.3 guest: Go explicit and
implicit prepared execution and configured Python prepared cursors ran without
SQL rewriting or interpolation fallback. An internal MariaDB API extension was
not needed for the tested cases.

The strongest objection is that this does **not** yet deliver one-line switching:
Connector/Python's default connection requests MULTI_STATEMENTS, which the
unchanged host rejects before PREPARE. A configured contrast succeeds, not the
default workflow. Completing the type/error/lifecycle surface and this connection
boundary is required before adoption. Do not merge this exploratory history as
production. Main integration, Qualification and release are not being decided.

## 1. Reviewed object and prior conditions

Base source: `2dc5247b28f849c9cbae3166744f39204a8d017f` (approved design and
the three linked source/design documents committed together).
Guest source origin: `13e253f4c22e01bc3bb16e2b20f00a4f74cd38bf`.
A2 host source: `e305ac90c208c7a063f5bf3068d465daab55f0da`.
B host source: `30ab38ea221ad60eecb7a8945d0c4feeedf42578`.
Branch: `experiment/prepared-bridge`. Subsequent report/consumer CLI changes do
not change these tested runtime identities. Exact objects, inventories and hashes
are retained in [evidence](v06x-prepared-spike-evidence/files.json).

Cross-check: [approved spike and maintenance budget](v06x-prepared-design.md),
[consumer sources](v06x-mysql-workflow-source-review.md),
[wire inventory](wire-gap-inventory.md),
[Snapshot contract](../decisions/snapshot-product-contract.md).

| Prior condition | Result |
| --- | --- |
| Three linked documents committed atomically | Satisfied by base commit; no dangling untracked design dependency |
| Experimental guest changes isolated; canonical source patch unchanged | Satisfied; `guest/experimental.patch` plus recorded resident overlay; fixed-input hashes |
| Metadata must be established, not invented or obtained by executing PREPARE | Satisfied for tested ordinary placeholders; section 2 |
| Ordinary prepared consumers, no interpolation substitute | Go satisfied for tested DB/Tx/Conn paths; Python configured paths only; default connection FAIL is retained |
| Fixed inputs and independent generation | Satisfied for one source-built Wasm and two independent Go translations; section 4. Not two independent Wasm builds |
| Existing failure oracles retained | J1 counterexample and protected controls reproduced; exact binding guard retained; section 5 |
| Rebase/maintenance ownership and cost exposed | Satisfied as a planning estimate and today's strict reapplication proof; section 6 |
| PASS/FAIL/SKIP and return to Human Review | This report; production approval pending |

## 2. Feasibility and ownership

MariaDB's public embedded API prepares, binds, executes, resets and closes on the
session's resident worker. Statement handles never cross session ownership;
closed handles and a handle from another/reopened slot return 1243. The guest
receives typed binary parameter payloads, not interpolated SQL. Normal text
commands, authentication and capability rejection were retained.

`mysql_stmt_param_metadata()` returns NULL in the pinned source and in the guest
probe. The same-version native server emitted ordinary placeholder descriptors
(name `?`, type NULL/6, charset 63, flags 128, length/decimals zero) for eight
SELECT/cast/NULL/DML/LIMIT examples. The adapter emits that observed placeholder
shape; actual result metadata comes from the embedded statement API. This is
bounded equivalence evidence, not proof for every possible statement or server
version. No query is executed during PREPARE. See native metadata JSONs and
`guest-go-and-direct.json` in the evidence index.

The authored C bridge lives in
[`prepared_spike.inc`](../../benchmarks/spikes/prepared-bridge/prepared_spike.inc)
and the experimental patch. Resident dispatch owns worker-local handles and
clears them on session close/stop. Host wire framing belongs to
`internal/mysqlwire/prepared_spike.go`; no-response CLOSE/LONG_DATA are serialized
without exposing the internal acknowledgement or using the text read-ahead
monitor. These are prototype choices requiring production cancellation review.

## 3. Results — native macOS arm64

Evidence filenames below resolve through the [hashed index](v06x-prepared-spike-evidence/files.json).
Consumer versions: Go 1.26.8 / go-sql-driver/mysql 1.9.3; Python 3.11 /
mysql-connector-python 9.4.0 (pure and C extension), PyMySQL distribution 1.2.3.
Reference: MariaDB 12.3.3 Linux arm64 container, pinned image in `fixed-inputs.json`.

| Check | Result | Evidence / limitation |
| --- | --- | --- |
| Embedded prepare/execute/reset/repeat/close; NULL/string/int64 | PASS | `guest-go-and-direct.json`; malformed command, cursor flag, foreign/stale/reopened-slot handle rejection included |
| Go DB/Tx/Conn Prepare; implicit parameterized Exec/Query | PASS | Same JSON; actual guest, writes, rollback/commit; interpolation disabled; explicit Prepare also tested with interpolation enabled |
| Native Go consumer control | PASS | `native-go-final-fixture.json` |
| Python default connection, pure and C extension | FAIL | `guest-python-and-wire.json`: 1235 unsupported connection capabilities before prepared execution |
| Python with only MULTI_STATEMENTS disabled; prepared=True | PASS for values | `guest-python-supported-flags.json`: repeated signed limit/Unicode/NULL, pure and C extension; no SQL changes |
| Configured Python pure writes/commit/rollback/BytesIO long data | PASS | `guest-full-consumers-supported-flags.json` |
| Configured Python C extension full scenario | FAIL | Same JSON: syntax-error assertion sees 2006 instead of 1064; earlier value/write/transaction assertions completed |
| Pure Python prepare syntax error | PASS | Error 1064/42000, guest and reference |
| C extension prepare syntax error | FAIL in guest **and reference** | `native-supported-flags.json`, `native-cext-isolated.json`: reference next SELECT still succeeds. Do not classify as a guest regression or silently relax expected 1064; root cause unresolved |
| Raw EXECUTE reuses parameter types | PASS | `guest-python-supported-flags.json`, native contrast |
| Raw LONG_DATA chunks then EXECUTE, CLOSE then immediate PING | PASS | Extended and full consumer JSONs; foreign/stale handle rejection |
| Text SQL/transaction/Snapshot/three Forks/shared-host cleanup | PASS | `smoke-current-lifecycle.log`; full B route smoke PASS |
| Unit wire codec tests | PASS | `wire-unit.log`; bounded types, not comprehensive protocol validation |
| Developer input/lifetime-binding tooling | PASS | `host-stage-binding-tests.log`, 28 tests |
| Python 3.14 with this pinned Connector/Python | SKIP execution | `native-consumers.log`: import fails because removed ssl.PROTOCOL_TLSv1; no monkeypatch or hidden dependency substitution |
| Native Ubuntu x86_64 | SKIP | No native runtime run in this spike; reference Linux arm64 container is not equivalent evidence |
| Performance, full framework/ORM acceptance, Qualification | SKIP | Not this feasibility gate; no speed claim |

The flag contrast disables **only** bit 65536. `connector-default-flags.json`
records that the pinned connector enables it by default; the host still rejects
it. This identifies a connection prerequisite for production; it does not approve
turning on multi-statement execution or a permanent user workaround. The raw
tests and Go tests are independent of that Python connection setting.

## 4. Fixed inputs, generation and honest failure history

MariaDB source `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`; lite4mariadb
`24be9371a2f6c71250a2356631ad6feab2280b02`; converter
`730057c146463f663e8774587bc96fb2bea91af8` with the existing **13** patches
unchanged. Exact order/hashes, archive/toolchain sources and options remain in
the committed release locks and retained guest/translation records. Build uses
LLVM 23.1.0, WASIXCC 0.4.7, sysroot 2026-07-03.1 legacy EH, Binaryen 133,
Go 1.26.8. Builder and native reference image identities are in `fixed-inputs.json`.

Source-built guest SHA256:
`e8f1b15e69194c860101496ed02ec684e34ad042bb3f6048630805ba656208ac`
(18,434,264 bytes); linked Wasm:
`c0527dffe15e20cbfe566b360665809a77bfc57eb7f8f70c367d8bb93d1e3ab0`.
Experimental patches reapply to pinned pristine sources without fuzz; actual
builder inputs match the strict reconstruction. See `patch-reapplication-corrected.json`
and `builder-patch-match.json`.

Two fresh translations A2/B independently produced identical **52 raw files**.
The two full installations contain 99 files: 98 match directly; their provenance
differs because installation inputs record different absolute translation paths.
This difference was retained, not normalized away. Running the official installer
on the two independently produced candidate modules with the **same B input
record** yielded **99/99 identical files including provenance**, checked byte
hashes. `independent-regeneration.json` retains all four inventories and the
common input digest. A2→B host diff is only documentation and test repairs.

B's full developer route, compile and smoke completed PASS, explicitly
**UNQUALIFIED**, host binary SHA256
`3a623cbb710693c2d82eff17f8d5065829bd5a11377c03c3b080a0221bcc67a4`.
Canonical release inventories/guard were not repinned or weakened for this spike;
experimental guest provenance remains ineligible for release.

Failed attempts remain evidence: first build intentionally stopped to fix an
uninitialized NULL-result length; restart initially rejected leftover empty output;
A installer rejected the unreviewed new guest lifetime bindings; A2 generated and
compiled but stale developer smoke used removed `_process`; its repaired first
attempt then correctly rejected a busy Snapshot. Repair uses existing
`wait_disconnected()` precondition and shared-host ownership checks; it does not
relax Busy/cleanup oracles. Explicit repaired A2 smoke and full B smoke passed.
No failed full-route receipt is relabelled PASS.

## 5. J1 rebase and failure oracle

The new guest changes absolute globals/TLS size, so the strict existing guest
hash/function binding gate rejected it. The owner script now explicitly lists
this one additional exact guest identity and exact reviewed function hashes;
old pins/negative checks remain. No wildcard or relocation normalization is used
by the installer. Fifteen malloc/join/free closure functions were compared:
structure unchanged, reviewed global/string relocations only; Fn131 unchanged,
Fn153 global +46528, Fn216 globals +46528 and TLS length 497→46321.
Allocation descriptor offsets +16/+40/+44 and lifetime controls are unchanged.
See binding/closure relocation JSONs.

The [fixture packager](../../tests/v06_prepared_thread_fixture.py) extracts actual
new generated functions, verifies exact bodies/readonly string, and rebases six
absolute image constants in a copy of the existing J1 fixture. Original oracle
source/assertions are untouched. `j1-identities.json` pins every extraction and
replacement. Unprotected heap **FAIL reproduced** (replacement canary 165→1;
two controls PASS). Protected heap and mmap, with and without `-race`, each PASS
early-free/completed/no-post-unlock-wake/detached-self-free. Logs and `j1-matrix.json`
are retained. Zero race reports are not a general shared-memory safety proof.

## 6. Remaining production work, cost and detection net

The feasibility question has a positive bounded answer. **General prepared
support remains unfinished.** Prototype limits: 64 statements/session,
64 parameters/columns, 4096-byte cell and 1024 result rows; incomplete temporal,
decimal and unsigned/type boundary coverage; no server cursor/FETCH or general
multi-result support. No-response failures currently close the wire connection,
not a complete native deferred-error model. Schema reprepare, cancellation,
disconnect/resource pressure, concurrent pools/Forks and full malformed input
coverage need production work. Public guides still describe the published product;
this experiment does not change its promises.

| Gap | Existing detection / required next work |
| --- | --- |
| Default Connector/Python connection rejected | Explicit spike oracle catches it; ordinary CI does not run this experimental guest. Resolve capability negotiation deliberately and test the unmodified consumer before adoption |
| Type/packet/error/lifecycle completeness | Limited tests do not cover missing cases. Implement production codecs/limits and add the acceptance matrix from the design; retain native C-extension discrepancy as a failing comparison until explained |
| New guest binding maintenance | Strict guest/function hashes fail closed, plus J1 oracle. Review absolute layout again on every guest update; current PASS proves today's binding only |
| Ubuntu and canonical adoption evidence | Unverified. Requires native Ubuntu tests, canonical patch/inventory ownership, clean independent rebuild/regeneration and normal source/release checks before integration |
| Performance/regressions beyond bounded smoke | Unmeasured; no inference from this functional spike. Use existing consumer/framework and release gates at the appropriate adoption stage |

No edits to MariaDB internal APIs were needed; upstream rebase surface is recipe
include, authored bridge, resident dispatch and explicit generated lifetime
binding. The latter is a concrete maintenance cost, not a hidden converter update.
The canonical patch and converter patch set stayed unchanged. Guest adoption must
promote the reviewed bridge into canonical ownership and update the relevant
inventories/default guest binding, not carry `experimental.patch` into release.

Planning estimate remains **5–10 additional engineer-days** for a production
candidate (2–4 codec/types, 1–2 ownership/errors/capability prerequisite, 2–4
consumer/regression/evidence/docs), plus build/CI wait. This is an estimate, not
measured effort or automatic approval; larger reprepare/cursor requirements need
another scope decision. Reserve 0.5–1 day per guest update for reapplication,
strict layout review and focused regression plus builds; today's zero-fuzz proof
does not establish future applicability. Multi-statement dump import remains a
separate potentially cheaper option, not a substitute for prepared support.

## 7. Reproduction and storage

See [commands](v06x-prepared-spike-evidence/reproduce.md), exact JSON/logs and
checksum index. Large receipts/logs are gzip-compressed losslessly; the index
records original and stored hashes. Temporary supported-flags scripts are retained
alongside the final CLI equivalents, so the actually executed source is available.
No generated Go was hand-edited. Disposable guests, generated copies, binaries,
SDK/module/build caches and completed worktree are removed after evidence and
branch preservation. This review does not promise full protocol support, a
performance improvement, Ubuntu acceptance or release readiness.
