# P2 isolated failure assessment — additional repair scope awaiting Human

P2 remains incomplete. The decision now is whether to authorize a bounded
extension covering embedded parameter binding and changed-result metadata.
**Recommend continuing with those two repairs**, first proving the required
native semantics in small controls before committing to any upstream edit.
The independent cases demonstrate user-visible failures on both platforms, so
retrying the unchanged CI or accepting its units would not resolve them.
The strongest objection is the maintenance cost of further MariaDB patches:
public APIs alone have not demonstrated the required behavior. Any additional
internal change needs this explicit decision under
[the approved stop condition](v06x-prepared-product-design.md#7-finite-implementation-and-acceptance-plan).
This is not main adoption, version placement or release approval.

## Exact candidate and evidence

Reviewed candidate/source_commit: d11f4ff3c2a42e6095aaa0d348de21369d2f3dd0,
branch experiment/prepared-product. No local changes existed when diagnosis began.
[CI39585983268](https://github.com/masahitojp/mariamem/actions/runs/39585983268)
passes source and both unit jobs; both runtime jobs fail only the additional
matrix. [Receipt](v06x-prepared-p2-isolated-result/receipt.json) records original
artifact hashes and the unchanged guest identity. Full captures:
[Ubuntu](v06x-prepared-p2-isolated-result/ubuntu-24.04-matrix.json),
[macOS](v06x-prepared-p2-isolated-result/macos-15-matrix.json).
Each of20 cases has its own host/runtime PID. Case results are identical across
OSes; PID diagnostics differ. This closes the previous harness-isolation gap,
not the implementation failures.

| Boundary | Both-OS result | Actual consequence |
| --- | --- | --- |
| Twelve additional scenarios | PASS against the saved native reference | DECIMAL, VARCHAR, three blob variants, TIMESTAMP, type reuse/changes, DML/warnings/recovery, commit/rollback, DATE SQL modes, schema type change and dropped column |
| Seven parameter type cases: BIT16, ENUM247, SET248, GEOMETRY255, INT24=9, YEAR13, NEWDATE14 | FAIL independently | EXECUTE times out with2013; following query fails with InterfaceError0. No binary row was captured |
| schema-add: SELECT * after ALTER ADD column | FAIL | Old execution returns2 columns; reexecution returns2057/HY000 instead of native3 columns. Following query fails2014, commands out of sync |
| Previous gates | PASS | Development SQL/transaction/Snapshot/Fork/Close smoke, exact binding plus mutations, P1, original22 EXECUTE cases and13 TIME cases |

The ordinary-driver frequency of the seven raw wire types is not measured.
These are parameter descriptor codes, not a claim that selecting a BIT/ENUM
column always kills a DB. No data corruption was observed in these captures.
Logs are empty, so a particular dynamic exit site is not proven.

## Source-supported causes and remaining uncertainty

Pinned MariaDB source_commit remains83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e.
These are source observations, separate from the measured outcomes above.

1. [libmysqld/libmysql.c:2850–2960](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/libmysql.c#L2850)
   copies MYSQL_BIND pointers, then its accepted-type switch rejects exactly
   these seven codes. Our guest/prepared_api.inc:295 closes the partially bound
   handle before freeing buffers and returns NULL; guest/resident.inc's reply
   owner treats a NULL response as terminal. This source chain is consistent
   with the timeout, but is not an instrumented proof of the exact exit site.
   Casting to another supported type is not yet a solution: metadata, NULL
   behavior, previous value and repeated descriptors must match native.
   [sql_prepare.cc:1188](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/sql_prepare.cc#L1188)
   forwards buffer_type to setup_conversion; preserving byte width alone does
   not establish semantic equivalence between types.
2. [libmysql.c:1764](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/libmysql.c#L1764)
   explicitly sets2057 when the result count changes. mysql_stmt_execute invokes
   this check after the server execution at2599–2613. reset/free_result at4620–4778
   flushes results but does not rebuild field_count/fields. Merely resetting or
   clearing old bindings therefore does not establish updated metadata. Our
   early ps_error return at prepared_api.inc:303 also skips normal result
   cleanup, consistent with the observed following-query2014.
   Cleaning up that error alone would not meet native successful reexecution.
   Never retry execution blindly: a statement may already have side effects.

A sound public-API solution has not been established. No assertion is made that
all possible public-API approaches are impossible. The bounded next step must
decide this concretely rather than weaken the native expectation.

## Proposed bounded continuation and acceptance

- Preserve all20 cases, original22/TIME13/P1 oracles and exact binding guards.
  First use small pinned-source controls to test parameter conversion/binding
  and changed result metadata independently of a whole guest rebuild.
- For the seven codes, require exact value/NULL/metadata parity, descriptor reuse,
  type transitions and healthy following SQL. Prefer an authored public-API
  bridge only if those controls establish equivalence; otherwise propose the
  smallest pinned experimental source change. Do not alias types by shape.
- For schema-add, preserve the original statement identity and expose the current
  descriptors/results from one execution. Verify subsequent SQL, count decrease,
  type changes, and a side-effect counter demonstrating no double execution.
  Respect old binding allocation lifetimes. Error cleanup is necessary but
  cannot replace successful native behavior.
- Any upstream change stays in guest/experimental.patch with exact preimage,
  ordered zero-fuzz application and postimage checks. Canonical source.patch,
  converter pins/13 patches and generated-source ownership remain unchanged.
  Rebuild normally; inspect/rebind the single guest identity and lifetime bodies,
  then repeat all existing actual runtime gates on both OSes. P6 independent
  regeneration remains separate unfinished work.
- Planning estimate for this extension:1–2 engineer-days for controls, a minimal
  candidate and focused tests, plus source builds/CI. This is an estimate, not a
  measured duration or delivery guarantee. Stop again before a broader upstream
  redesign, SQL rewrite, execution retry or oracle/scope reduction. If the small
  controls cannot preserve semantics, return their exact counterexample and a
  revised scope rather than inventing a passing substitute.

## Prior conditions and detection net

The approved TIME repair remains verified for its35 execution/TIME cases;
no regression is indicated there. Existing actual matrix detects both new
defects, while source/unit gates alone demonstrably do not. Current P1 allocation
identity and mutation checks pass on both OSes. The previous C-extension
consumer disposition is not reopened. No new current-usage contract, canonical
generated tree, release ledger or public API is changed by this diagnosis.
No missing inventory update is introduced by a docs/evidence-only change.

Unfinished conditions are P2's eight cases and the rest of P2–P6 acceptance,
including P3 chains, P4 resource/failure hardening, P5 consumers and P6 canonical
independent generation. Current investigation inspected these20 results and
their immediate source owners; it is not a general MariaDB API audit, performance
assessment or Qualification. No runtime fix, generated edit, main merge or
release is performed here. Findings are saved separately from historical reports.
