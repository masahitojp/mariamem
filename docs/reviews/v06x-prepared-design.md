# v0.6 prepared statements — implementation alternatives and Human Review

2026-10-18. Local source basis: `61c5d12c13c3cc7fc97c4a88d2f893054c06f589`.
Design only: no runtime change, new build, or consumer acceptance run.

## Requirement and decision boundary

The Human approved Python and Go prepared support as a necessary part of the
one-line-switching north star. Requiring application SQL changes, disabling
prepared cursors, or enabling interpolation is not completion of this requirement.
Routing a connection and preserving its statement semantics are separate jobs.

Basis: [product direction](v06x-kickoff-notes.md#11-north-star-and-capability-coverage-matrix-ideal-driven),
[workflow options](v06x-workflow-design-options.md),
[consumer source findings](v06x-mysql-workflow-source-review.md),
[wire inventory](wire-gap-inventory.md), and the
[Snapshot contract](../decisions/snapshot-product-contract.md).
The requirement is approved. On 2026-10-19 the Human approved the bounded
spike below, with experimental-patch isolation, fixed inputs, independent
regeneration, PASS/FAIL/SKIP evidence and a return to Human Review. Production
implementation remains a separate decision. This does not move guest initialization optimization out of v0.7.

## What the source establishes

The current host dispatch rejects prepared commands. The guest bridge exposes
text execution and hex-encoded result cells, not statement handles and typed
bindings. Explicit Go Prepare remains prepared even with interpolation enabled.
Connector/Python's ordinary prepared execute performs RESET before EXECUTE.
The pinned consumer sources and lifecycle distinctions are in the source review.

MariaDB 12.3.3 source commit
`83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e` contains an embedded implementation:

- [lib_sql.cc](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/lib_sql.cc):
  `embedded_methods` connects prepare-result handling, statement execution and
  binary result readers. `emb_stmt_execute` passes bound parameters to the engine.
- [CMakeLists.txt](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/CMakeLists.txt):
  embedded sources/exports include the `mysql_stmt_*` API.
- [libmysql.c](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/libmysql.c#L1863):
  **`mysql_stmt_param_metadata` always returns NULL**. Parameter count and result
  metadata do not establish that the public embedded API supplies all metadata
  required by a wire PREPARE response.

This proves an upstream implementation exists, not that newly reachable paths
already work in this WASIX guest and Generated Go. Parameter metadata is the first
feasibility question: compare the same-version server's wire behavior and source;
use equivalent placeholder descriptors only if that equivalence is established.
Do not invent types, execute SQL during PREPARE, or silently omit required packets.
If a small embedded bridge extension is needed, report its scope before adoption.

## Alternatives

| Method | Benefit | Semantic / maintenance cost | Assessment |
| --- | --- | --- | --- |
| Host interpolation and statement emulation | Reuses text guest; avoids guest regeneration | Host must reproduce prepare-time errors, metadata, types, statement state and schema-change behavior | Low initial coding cost does not establish equivalent support; not recommended as default |
| Text SQL PREPARE / EXECUTE bridge | Engine parses prepared SQL | Session variables, binary values and metadata still need a bridge; current single-result interface is insufficient evidence | Retain as fallback investigation, not a proven cheaper equivalent |
| Guest `mysql_stmt_*` bridge plus host binary protocol | Engine owns parsing, binding and execution; host owns client framing | Typed transport, metadata gap, statement cleanup, guest rebuild and reproduction | Preferred candidate; first prove the missing boundary |
| Embedded internal protocol/packet bridge | May expose metadata and engine packet production directly | Strong coupling to upstream internals and transport assumptions | Reconsider only if the public embedded API cannot meet the boundary economically |

None is selected as production implementation yet. The recommendation follows
the required behavior, not a prior assumption that wire work must be host-only.

## Proposed ownership and protocol boundaries

- One wire session owns its statement table. Guest handles belong to that
  physical session's worker and generation, never to a global statement ID.
  Slot reuse, disconnect and reopen invalidate old handles. A logical Go DB Stmt
  may prepare separately on several pooled physical connections.
- Snapshot/Fork transfers database state, not connections or statement handles.
  Preserve existing busy/disconnected Snapshot preconditions. Children cannot use
  another child's handles; closing a baseline does not close admitted children.
- Extend the framed guest API explicitly for prepare, bind/execute, reset, close
  and long data. Validate opcode, payload lengths, counts and handle ownership;
  incompatible host/guest schemas fail closed. Do not serialize native pointers.
- Parameter values retain NULL, byte lengths, signedness, numeric widths,
  decimal precision and temporal representation. Results need binary-row encoding
  and metadata, not a generic string conversion. Define repeated EXECUTE type
  reuse and reset/long-data lifetime explicitly.
- PREPARE/EXECUTE/RESET have responses; CLOSE and SEND_LONG_DATA have no response
  on the client wire. See the official
  [CLOSE](https://dev.mysql.com/doc/dev/mysql-server/latest/page_protocol_com_stmt_close.html)
  and [LONG_DATA](https://dev.mysql.com/doc/dev/mysql-server/latest/page_protocol_com_stmt_send_long_data.html)
  descriptions. Internal acknowledgements must not escape as client packets.
  Current `callQuery` reads concurrently to detect disconnect/unexpected input;
  reusing it for no-response commands would misclassify legitimate following
  commands. Design serial dispatch and cancellation together, with bounded buffers.
- Preserve text execution, capability negotiation, authentication, session
  initialization, original SQL errors and fatal-transport handling. Do not enable
  unsupported capability bits merely to make a client proceed.

Server cursor/FETCH, multiple result sets and modern optional protocol flags
need explicit coverage decisions before claiming general support. They are not
counted complete by the bounded spike. COM_STMT_RESET is not COM_RESET_CONNECTION;
pool-reset support remains a separate capability-map item.

## Proposed bounded spike and stopping point

Use an isolated experiment branch; retain fixed guest/converter inputs and
canonical generation ownership. Two steps, with a stop between them if the API
boundary is not viable:

1. Prove embedded prepare metadata/counts, typed binding and binary-result
   reconstruction through the actual guest. Check SELECT with NULL, integer,
   string/binary parameters; a write inside rollback; prepare-time syntax error;
   reset, repeat execution and close. Compare metadata/values/errors with native
   MariaDB 12.3.3 where available and pin its identity. Record missing reference
   environments as SKIP, not equivalence.
2. Connect a minimal wire adapter to one ordinary Connector/Python prepared
   cursor and Go explicit Prepare plus parameterized Exec/Query without
   interpolation. Check a second session, invalid/stale handle rejection and
   no-response CLOSE/LONG_DATA followed immediately by another command. This
   establishes feasibility, not full consumer coverage or production readiness.

Deliver: source diff, exact inputs, PASS/FAIL/SKIP matrix, metadata resolution,
remaining command/type/lifecycle coverage and updated implementation estimate.
Stop for Human Review before production implementation. Failure or time exhaustion
is an incomplete spike with the precise blocker, not permission to replace
prepared support with interpolation. No main integration or release is included.

Planning estimate, not measured duration or an approved budget: **1–2 engineer-days
for the spike**, assuming existing build tooling works. Newly reached converter
issues or a larger metadata bridge require a revised scope. CI queue/build wait
is additional; do not promise a two-day result regardless of those dependencies.

## Guest maintenance and rebase budget — approval condition

The spike must report the exact recipe/overlay/upstream changes separately, not
just runtime speed or functional PASS. `guest/source.patch` stays unchanged in
the experiment; temporary recipe/source changes live in
`guest/experimental.patch`. New bridge inputs must be bound in preparation and
regeneration inventories. At adoption, recipe changes become maintained canonical
patches/overlays rather than an untracked experiment dependency.

Reserve **0.5–1 engineer-day within the spike estimate** for input ownership,
regeneration and a bounded reapplication check: apply the experimental changes
from pristine pinned inputs with zero fuzz, identify upstream-context dependencies,
and identify which changes need review on the next MariaDB/lite4mariadb update.
This establishes reproducibility at today's pin, not future-version applicability.
For production planning, provision **0.5–1 engineer-day per future guest update**
for rebase/rebuild and focused prepared regression, plus full generation/CI wait;
this is an estimate to revise from the spike, not an observed recurring cost.
If bridge changes require edits to MariaDB internals or exceed that maintenance
allowance, stop and present the changed ownership and budget at Human Review.
Do not absorb those changes silently into the approved spike.

Prepared is priority #1 for ordinary Python/Go behavior, not the only import
option. The pinned lite4mariadb recipe already offers `l4m_exec_multi` and opens
with CLIENT_MULTI_STATEMENTS; mariamem deliberately disables that flag for its
resident connection in `guest/source.patch`. Restoring multi-statement execution
still needs result draining, error/session semantics and a host/guest API, but may
be cheaper for dump import than prepared support. It remains an independent
capability and is not required to be implemented in this spike.

Results of the authorized spike: [Human Review and evidence](v06x-prepared-spike.md).
The historical proposal above is retained; the results document owns the current ask.

## Production work and acceptance after feasibility

Provisional effort: **5–10 additional engineer-days**, not a delivery commitment:
roughly 2–4 for typed transport/wire codec, 1–2 for lifecycle/error/resource
handling, and 2–4 for consumer/regression tests, generation evidence and docs.
Re-estimate after the spike; internal-engine changes or broader cursor/multi-result
support may exceed this range and require another scope decision.

| Boundary | Required evidence before adoption |
| --- | --- |
| Types and packets | NULL/zero parameters, signed/unsigned limits, decimal, binary/NUL/Unicode, temporal precision; metadata, null bitmap, truncation and malformed-length rejection; repeated EXECUTE with and without new type descriptors |
| Engine behavior | SELECT/writes, affected rows/insert IDs/warnings/errors, prepare-time failures, schema changes/reprepare, commit/rollback; compare to the pinned native engine |
| Lifecycle | Several statements/sessions, DB/Tx/Conn Go Stmt ownership, pool reconnection, reset/long data/close, stale IDs after slot reuse, independent Forks, cancellation/disconnect cleanup |
| Consumers | Go explicit Prepare even with interpolation enabled; implicit fallback with interpolation disabled; Python pure and C-extension prepared modes separately; unsupported modes recorded, not silently replaced |
| Regressions | Existing text SQL, auth/capabilities, connection initialization, Snapshot/Fork/Close and failure oracles; native macOS arm64 and Ubuntu x86_64 evidence |
| Generation | Canonical guest rebuild, Wasm→Go generation, independent reproduction, exact identity/provenance and source/release guards |

Ownership starts at `guest/wire_core.inc` / `guest/resident.inc`, their preparation
inputs in `scripts/prepare_guest.py`, host guest-result/transport types and
`internal/mysqlwire`. Changes to upstream source belong to the canonical patch
at adoption (experimental patch during the spike). Do not edit Generated Go.
Update source manifests, generated input inventories and provenance as required
by the actual changed inputs. Public docs currently promise text-only support;
revise that contract only with accepted implementation and evidence.

## Human Review — spike approved, production decision pending

**Recommendation accepted for the bounded embedded-API spike above**; full
implementation is not approved. Decisive reason: it preserves engine-owned prepared semantics
without asking users to rewrite normal Python/Go code, and the upstream embedded
implementation provides a concrete starting point.

**Strongest objection:** this is not merely a few host command handlers. The
public embedded parameter-metadata API is a stub; binary results and lifecycle
handling add a real guest/host integration burden. The spike must resolve that
boundary before the production effort is accepted. If it cannot, return a
specific design alternative and cost rather than weakening the north star.
