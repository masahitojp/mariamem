# Minimum routine bootstrap — implementation decision

Status update, 2026-10-20: the Human approved the bounded implementation scope
**including the product-managed proc-structure boundary and rejection of
incompatible restored baselines**. Version placement, integration and release
remain separate decisions. The design/recommendation below records the earlier
Human Review at1f4599f; its pending-approval wording is historical.

2026-10-20. **Decision requested: approve a bounded production-candidate
implementation of the minimum routine bootstrap below? Recommend approval.**
Users should be able to prepare procedure/function fixtures without manually
constructing MariaDB's internal table. The real-guest spike established that
the existing engine executes the minimum cases once its official proc table
exists. Put initialization inside the guest, before ready, and preserve that
state through the existing Snapshot lifecycle.

The strongest objection is that a minimal bootstrap is not a complete MariaDB
installation: account/DEFINER behavior, restored state and additional entrypoints
still need explicit acceptance. In particular, distinguishing Fresh from Fork
needs a small handwritten host change; a guest-only existence check would hide
damaged or deliberately modified baselines. The design includes that boundary
and finite failure tests. Do not adopt the candidate if they fail. No production
implementation or target version is approved by this design task; prepared/
multi-statement scope, integration, Qualification and release remain separate.

## Basis and what the Human approved

Source/evidence basis: **`46ff987f85b576d6664f3cafcc89e481326de51f`**, branch
`experiment/guest-system-schema`, and its
[feasibility report](v06x-guest-system-schema-spike.md). Main at design start is
`de0e08a9c4248969a7522abebfdee8aea6ef9657`; this document is on
`experiment/routine-bootstrap-design`, based on the evidence branch. It does not
merge exploratory history onto main.

The Human's “proceed” follows the recommendation to make minimum initialization
the next design subject. It authorizes this design, not an inferred routine
release version or a production implementation. Cross-check the
[prepared design](v06x-prepared-design.md),
[north star](v06x-kickoff-notes.md#11-north-star-and-capability-coverage-matrix-ideal-driven),
and [Snapshot product contract](../decisions/snapshot-product-contract.md).
Historical reports remain unchanged.

Established: six text-SQL cases match native after official proc DDL; base89
statements succeed; full fix has an unaccepted1193 on event_scheduler; deliberate
comment-nullability mismatch produces1728 and repairing it restores the cases.
The same Wasm, converter13 patches and host binary were used. See the report's
indexed raw evidence; this design adds no runtime measurements or PASS claims.

## Options and ownership

| Option | Benefit | Cost / semantic consequence | Judgment |
| --- | --- | --- | --- |
| Guest minimum bootstrap before ready | One engine-owned path for Go/Python; failure prevents exposure of a partial DB | Version-bound DDL, guest rebuild and explicit Fresh/Fork context | Recommend |
| Host bootstrap before returning a public DB | Can avoid embedding SQL in Wasm; possible through an internal connection | Must gate every endpoint/readiness path and manage a bootstrap session, SQL state and wire dependencies | Viable alternative, larger host/session coupling for this change |
| Same CREATE IF NOT EXISTS on every start | Smallest apparent control flow | Silently recreates a missing table in a restored baseline; existence does not establish compatible definition | Reject |
| Whole install/upgrade SQL | Wider system-schema setup | Whole new install is a different script set; current full fix fails1193, with much more work | Reject for this routine scope |

mariamem owns the initial implementation and its pinned initialization contract.
An upstream lite4mariadb proposal may follow, but is not a dependency for this
bounded candidate. Extract DDL from the **adopted MariaDB12.3.3 archive**, not
lite4's embedded13.1 source merely because the current lines happen to match.
No events, account-management implementation, sys/help installation, package
support or new public option is included. Version placement remains a Human
planning decision; this design does not add routines to prepared v0.6.0 scope.

## Technical dependency without combining decisions

The six-case feasibility result used the experimental host/guest result-draining
path. Current main `internal/mysqlwire/wire.go:21` does not advertise
CLIENT_MULTI_RESULTS or CLIENT_MULTI_STATEMENTS, and its guest bridge has not
adopted the experiment's ordered result chain. Initialization itself needs
neither binary prepared statements nor multi-statement SQL. However, a public
claim that CALL returns multiple results requires the separate text multi-result
capability/framing/draining implementation to be accepted and verified. Terminal
OK, later errors and next-command reuse are part of that dependency.

Do not silently transplant the whole prepared experiment, weaken the six-case
oracle, or call the bootstrap alone complete public routine support. A candidate
may be developed in isolation, but its product adoption waits for an accepted
text multi-result path (or returns a concrete scheduling decision to the Human).
This does not expand, approve or defer the existing prepared/multi-statement
scope, and it does not imply prepared CALL is covered.

## Execution and lifecycle contract

Recommended placement: `guest/resident.inc:main`, after successful `l4m_open`
and the existing auth diagnostic early-return, before closing `g_mysql`, creating
worker slots and emitting ready. Reuse that private bootstrap MYSQL connection.
Do not move initialization into each SQL session or add a public-client call.

The actual library path in
[`runtime_instance.go`](../../internal/generatedgo/runtime_instance.go) sets
args to `mariamem` for both modes and maps restored entries with
`MapPreparedHandles` before executing the guest. Thus `--restore-snapshot` is
**not** the library Fork signal. The `transfer` parameter is an export boundary,
not a substitute restore flag.

Propose an internal host-authored environment value,
`MARIAMEM_BOOT_MODE=fresh|restore`, selected from the same `restore != nil`
condition that controls mapping. Construct it explicitly alongside the existing
timing value; do not inherit an ambient user value. No Go/Python public API
changes. The diagnostic generated driver must set the same mode from its own
restore source; auth-key diagnostic modes retain their existing bypass/behavior.
Missing/unknown mode in a normal startup is an initialization failure, not an
implicit Fresh fallback. The legacy restore CLI path must agree with the mode.

| Phase | Fresh | Fork / private restored handoff |
| --- | --- | --- |
| Before engine open | Fresh backing selected by host | Existing identity-checked baseline mapped as today |
| Routine schema | Create mysql and official proc table exactly once in this new DB | Read existing definition; do not create/ALTER/repair/drop it |
| Validation | Check expected table structure after creation | Check the same expected structure; fail on missing/incompatible table |
| Ready | Only after validation and bootstrap connection cleanup | Only after validation and normal restored startup |
| Capture/Close | Existing engine shutdown and sealed backing capture | Existing ownership/isolation contract; no extra content scan or persistence |

Fresh means a new product-owned empty datadir. Unexpected existing proc/schema
state is an error, not an invitation to overwrite it. No global process cache
or “already initialized” boolean is authoritative for different DBs. A successful
baseline includes the system table and the user's routine rows. A child may
CREATE/DROP routines independently; those **row** changes must not affect parent
or siblings. A new Snapshot from that child preserves its own routine state.

**Proposed explicit boundary for Human approval:** the proc *structure* is
product-managed. An application may read it and create/drop routines, but a
baseline whose internal proc structure was dropped/altered is rejected at Fork
startup rather than silently repaired. This changes when such a misuse fails;
it does not prohibit ordinary routine changes. Do not tighten this implicitly.
Old guest identities remain rejected by existing checks; no saved Snapshot API
or cross-version migration is added.

## Minimum SQL and structural validation

Use only the official proc DDL plus required mysql database/context setup. Keep
skip-grant-tables and existing authentication/session defaults unchanged.
No synthetic mysql_version variable, whole base/fix script or1193 allowlist.
The proc table remains Aria with the pinned22-column definition and primary key
`(db,name,type)`; no substitution of another engine or hand-shortened definition.

Use a dedicated bootstrap helper/include. Save/restore database selection,
charset/collation and sql_mode if changed; never change process/global defaults
to make bootstrap pass. Restore the expected private connection context before
closing it; ordinary workers still initialize their own connections normally.
On any failed step, capture its stage, MySQL errno/SQLSTATE/message before cleanup.
Do not issue more SQL on a broken connection or report zero as successful errno.

Recommended read-only validation is targeted table metadata, not executing a
temporary user routine or scanning routine bodies. Check column order/name/type,
charset/NULL flags, engine and primary-key order against a reviewed normalized
signature of the pinned definition. Public metadata queries such as SHOW FULL
COLUMNS/SHOW INDEX plus engine metadata can implement it; the precise normalized
representation must be fixed by real-guest fixtures in the candidate, not guessed
from SQL formatting. Do not compare an unnormalized SHOW CREATE string or claim
that CREATE IF NOT EXISTS invokes MariaDB's intact-table checker.

This is deliberately stricter about product-owned structure than MariaDB's
prefix-compatible intact-table check. It is not a byte-corruption detector or
a replacement for existing strict transfer/oracle checks. Retain1728 in the
independent SQL failure oracle even if the new pre-ready structural check detects
the same mismatch earlier. Both assertions have separate homes: SQL-only failure
fixture and production startup rejection fixture. A startup rejection does not
erase the earlier detector's coverage.

## Failure and cleanup

No ready frame/listener admission on bootstrap or validation failure. Emit a
stable `routine_bootstrap` diagnostic with operation and error details, then
close the private MYSQL connection/server using the existing cooperative cleanup
path and report startup failure. Do not route it through the existing RSA-specific
`l4m_open` error message. Existing startup error propagation can carry the stage;
do not invent a public error-code family without reviewing the actual mapping.
Unknown mode, metadata-query error, unexpected Fresh state, DDL failure and
incompatible restored structure all fail explicitly. No retry-as-Fresh,
automatic repair, silent text fallback or partially initialized return.
For Fresh failure with matching artifacts, the diagnostic should identify a
bootstrap/product failure and the input identity for a bug report. For modified
restored structure, explain that the baseline must be prepared again from valid
inputs. Do not ask library users to run install-db or construct mysql.proc.

Tests must verify no endpoint, active slot, mapped-baseline lease or worker is
left owned by the failed DB, while an unrelated DB/baseline stays usable. This
uses the existing cooperative shutdown contract, not a new forced-stop promise.

## Source/generation boundary and maintenance

| Owner | Candidate change |
| --- | --- |
| guest resident + new authored bootstrap include | Hook/helper and fixed metadata signature; isolate prototype changes in experimental.patch/overlays until adoption |
| scripts/prepare_guest.py | Deterministically extract exactly the pinned proc DDL into a generated C include; copy the authored helper through the explicit overlay list |
| Existing source/guest input records | Record MariaDB commit, whole SQL-file hash, extracted DDL/signature hashes and prepared-output hashes; no fuzzy anchor or ignored mismatch |
| internal/generatedgo/runtime_instance.go | Small boot-mode assignment; this file is explicitly HANDWRITTEN_FILES-owned, not transpiled Go |
| scripts/generate_runtime.py:adapt_driver / diagnostic driver owner | Deterministic diagnostic mode assignment; update its pinned preimage/candidate inventory as required, never edit generated main.go |
| Generated Go / release inventories / provenance | Fresh normal generation and independent comparison; update guest/data identities and exact lifetime binding only after reviewing actual output |

The extraction step must verify the adopted source file and find exactly one
expected DDL; upstream formatting/schema drift is a maintenance failure to
review, not a reason to silently widen matching. Record the generated include in
prepared-source output identity, as auth/diagnostic headers are today. Retain
upstream copyright/license attribution for the SQL-derived include. Keep the
converter SHA and its13 existing patches unchanged. Preserve release rejection
of experimental patches and all source/license/identity/J1 guards.

For every MariaDB update, review proc DDL, normalized metadata and source intact
definition together, then rerun source-bound negative/positive fixtures. Reuse
the existing guest-update inventory; do not build a multi-version schema manager.
If incompatible old data migration becomes necessary, stop and propose separate
scope. Product Snapshots are process-local and do not require that migration now.

## Finite acceptance and cost before adoption

| Gate | Required evidence | Current coverage |
| --- | --- | --- |
| Metadata/signature and extraction | Pinned positives; changed SQL/anchor/NULL/type/key/order rejected; explicit owner hashes | New tests needed |
| Fresh readiness | Routine usable immediately through Go/Python normal connections; no connection-default changes | Post-ready feasibility only |
| Restored readiness | Seed routines, capture, independent Fork calls/row changes, recapture, baseline Close with live child | Ordinary Snapshot smoke only |
| Failed startup | Missing/modified proc and injected DDL/metadata errors reject before ready, cleanup and unrelated DB health | SQL-only1146/1728 oracle exists; new startup oracle needed |
| Mode transport | Fresh/restore and diagnostic/auth modes; missing/invalid values; inherited ambient value ignored | New tests needed |
| Consumers | Existing six-case native comparison; normal text CALL via Go and Python; prepared bridge regressions remain independently gated | Six text cases feasible; prepared CALL unverified/excluded |
| Generation/platform | Formal build, independent regeneration, exact identity/provenance and related guards; both supported OSes | Old unchanged guest evidence only |
| Cost | Fresh ready cost and Fork validation cost separately, small paired diagnostic cohort | Existing post-ready SQL cost only; no ready-gate target promised |

No whole-guest race census, engine rewrite, general compatibility discovery,
performance target or release acceptance is part of this implementation gate.
Prototype PASS must not be promoted to production/platform PASS. If metadata
normalization cannot be fixed, restore fails, cleanup is not preserved or an
internal MariaDB API extension proves necessary, report the blocker and revised
scope before widening work. Do not substitute weaker assertions.

Planning estimate, not a commitment: about **1.5–3 engineering days** after
implementation approval, split between source/helper/mode tests (0.5–1), real
guest and lifecycle/consumer checks (0.5–1), and regeneration/platform evidence/
docs (0.5–1). CI elapsed time, unexpected blockers and final Qualification are
separate. The few-millisecond post-ready feasibility observations are not a ready-time or
Fork budget. Do not make upstream acceptance a hidden dependency.

This task changes documentation only. No build, runtime test, implementation,
version assignment, main integration, Qualification or release is performed.
