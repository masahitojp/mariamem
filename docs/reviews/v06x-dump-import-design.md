# Dump preparation — bounded comparison proposal

2026-10-24. Design source_commit:
`82877a2fc1d87d0d7cfe130c5467d3625bb6e16a` (adopted main).
This is the next design decision after migration recipe adoption. It reuses
existing source findings; no fresh dump, parser prototype, client import or
native execution is claimed here.

## Human Review — one decision now

**Recommend a bounded comparison spike of an external native client and an
in-process library reader, using the same freshly produced application dump.**
The question is which path lets a user who already has data prepare a correct
baseline with the least extra setup, while keeping errors understandable.
The library reader is a candidate, not a selected product implementation/API.

The strongest objection is parser maintenance: a seemingly small SQL-file helper
can become a second client with format/version-dependent behavior. Retain the
native client as a real alternative and a differential reference; if the reader
cannot preserve the selected format with a small explicit boundary, recommend
the external-client recipe or further design instead of stripping input. This
comparison avoids committing to an importer simply because a migration callback
worked. Approval sought is for this spike only, not productionization, main
integration, a version promise or release.

## Existing evidence and what this adds

- The [migration recipe](../preparing-test-data.md) and
  [main adoption](v06x-preparation-migration-main-adoption.md) establish explicit
  preparation -> disconnect -> consuming Snapshot -> independent child tests.
  Main CI40081512909 and Development checks40081512903 passed at82877a2.
  They did not read a dump file.
- The [preparation/import alternatives](v06x-preparation-import-design.md#following-dump-decision--still-required)
  already require a freshly produced, identified application dump. Native client
  and library reader remain alternatives; the former is not a selected mandatory
  user dependency.
- The [pinned dump inventory](v06x-mysql-workflow-source-review.md#3-concrete-preparation-inventory)
  has only an upstream decimal expected-output segment, including executable
  comments and a sandbox directive. It is not an executed whole application dump.
- Procedures/functions and text multi-results are now adopted. That permits
  testing a richer input; it does not establish SQL-client directive parsing.
  Packages stay outside product support and testing; events remain an embedded
  restriction. No new packages/events acceptance is proposed.

## Alternatives to compare

| Path | User setup | What the spike must establish |
| --- | --- | --- |
| External MariaDB/MySQL client | Install/version-manage a compatible executable and point it explicitly at the preparation DB | Does the selected client actually connect/import into this guest, preserve the input and expose a useful failure? |
| Library reader plus existing driver | Supply a file and preparation connection; no additional client executable if feasible | Can a bounded reader preserve statements/directives and identify failures without rewriting database semantics? |

Sending a whole file through cursor.execute or enabling MULTI_STATEMENTS is not
assumed sufficient. Client commands such as DELIMITER need an explicit owner.
The reader would frame SQL, not implement SQL execution; the guest still executes
SQL and interprets executable version comments. Existing parsers may be inspected
before choosing a minimal prototype, but no dependency is approved here.

## Fixed input and scope before execution

Create one small repository-authored application schema/data set, distinct from
an external legacy app. Produce its dump with an identified MariaDB12.3.3 native
server/client, rather than hand-writing something described as tool output.
Use ordinary InnoDB schema, constraints and rows, plus one procedure and function.
Include exact decimals, NULL/empty/Unicode values, binary bytes and text with
quotes, backslashes and semicolons; routine bodies must require statement framing.
Record actual emitted directives/comments before declaring the reader boundary.

Pin source_commit/tag_object_sha with git_identity where Git is used. Record
native server/client version, executable hash or platform-specific image digest,
architecture, command/options, source schema/seed hash and resulting dump SHA256.
If a matching producer/client cannot be acquired, report the missing input and
stop rather than substituting an unrecorded version. Docker may be development
reference tooling; it does not become a required mariamem user dependency.

This first corpus deliberately fixes one producer family to separate reader
behavior from engine differences. MySQL-produced dumps, other versions and
externally supplied legacy apps remain explicit follow-ups before any broader
compatibility claim. Their version placement is not decided or silently removed
from the capability map by this spike. SQL/CSV/data-directory import is not one
undifferentiated format promise.

## Execution and success oracles

Use `experiment/dump-import` and disposable budgeted workspaces after approval.
Keep guest/converter/runtime/product API unchanged; prototype code is test-only.
Build one source-identified Go host per OS and reuse it with hash/Go-stamp checks
where practical. Use the existing supported driver and explicit preparation URL;
no preparation routing or original application connection is involved.

1. Fix producer/options and save the original dump, its bytes and input manifest.
   Define recognized client commands from that observed input. Preserve SQL and
   executable comments; DELIMITER changes framing only. Do not remove routines,
   rewrite engines/collations, or disable errors to make the file import.
2. Import the exact dump into a clean native12.3.3 DB with the native client.
   This is the reference, not a hand-authored SQL reconstruction.
3. Import the same bytes into fresh guest sources using (a) that client and
   (b) the reader/driver candidate. Native-client-to-guest feasibility is itself
   measured; a failure there is not silently counted as a library success or
   evidence that the guest is generally incompatible.
4. Compare tables/columns/constraints, engine/collation, exact row values and
   procedure/function behavior against the native reference. Define comparison
   normalization in advance for volatile metadata, not broad text replacement.
   Drain any returned results and demonstrate a subsequent SELECT still works.
5. Disconnect, capture and run two ordinary application child tests. Commit a
   change in the first; the second must retain the imported baseline. Reuse
   existing isolation oracles rather than changing their meaning.

The functional matrix runs on macOS arm64 and Ubuntu x86_64. Use Python3.11/3.14
for the library candidate if proposed for the supported Python entry. This is
not another general routing/xdist census: the existing worker-local lifecycle
is retained; new tests target dump framing, execution and failed import.

## Failure oracles and diagnostic boundary

- Inject one known-invalid SQL statement after some valid changes. Require its
  expected errno/SQLSTATE where available, phase and original file location;
  unrelated connection/parser errors are not accepted as that oracle.
- Include malformed framing and an unsupported client command, such as SOURCE.
  Reject with a specific reader/directive reason and location; do not silently
  skip it or open another file. Do not reinterpret every SQL error as a parser
  problem or MySQL/MariaDB incompatibility.
- A failed import never returns a usable baseline or attempts Snapshot. Record
  partial DDL/data separately: discarding the source is not transactional rollback.
  Close import connections/processes and verify host/directory cleanup.
- Diagnostics identify the failing route, stage, statement ordinal and line/byte
  span in the original file, plus preserved native cause. Include one concrete
  next action based on known evidence. Do not expose credentials or dump values
  by default; exact injected SQL is synthetic test evidence only.
- Native-client failure captures exit/error output without continue-on-error
  mode. Compare available location/cause quality honestly with the reader; do
  not require client output to have an API field it does not provide.

For a reader, preflight of unsupported client commands is desirable before
execution, but SQL failure can still leave partial changes. The preparation
callback must re-raise and let the existing lifecycle discard that source.
No retry, automatic repair or partial-baseline recovery policy is introduced.

## Completion and stopping conditions

Return a PASS/FAIL/SKIP matrix for each route/OS/interpreter actually exercised,
source/tool/dump/host/guest identities, original input and raw logs, comparison
results, exact failure observations, reproduction instructions and a small
setup/maintenance comparison. No user-time or performance claim without a
measurement. SKIP is not PASS; a blocked producer/client is reported explicitly.

Recommend one of: productize a bounded library path; document an optional
external-client recipe; continue a concrete missing-input/design check; or defer
this format with a clear reason. A failed candidate is still a useful comparison
result, not completion of dump support. If guest/runtime changes are needed,
identify the blocker and return for a separate scope decision. Do not perform
those fixes inside this spike. End with Human Review, without productization,
main integration, Qualification or release.

## Planning-review limits and detection net

Current CI does not execute either dump route and cannot detect directive,
framing, location or partial-import defects. Migration CI is not substituted.
The proposed spike must add exact output/failure classification and defect
mutations before treating its native matrix as evidence. No unmet productization
condition is hidden as a passed test; all dump execution remains unverified.

No API/contract/generated-source or release-ledger change is proposed. User docs
still describe the migration recipe, not an importer. Broader diagnostics,
Django/mysqlclient and live/reset retain their separate decisions.

Basis: [capability map](v06x-capability-map.md),
[workflow alternatives](v06x-workflow-design-options.md),
[Snapshot contract](../decisions/snapshot-product-contract.md),
[routing contract](../decisions/connection-routing-contract.md).
