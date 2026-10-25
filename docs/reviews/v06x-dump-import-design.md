# Dump preparation — bounded comparison proposal

2026-10-24. Design source_commit:
`82877a2fc1d87d0d7cfe130c5467d3625bb6e16a` (adopted main).
This is the next design decision after migration recipe adoption. It reuses
existing source findings; no fresh dump, parser prototype, client import or
native execution is claimed here.

2026-10-25 review response: the fixed-input decisions below address the Human's
conditions on design candidate `76990376eaa5fcf24d6aab9cf62d1358e59bab10`.
The review recommends conditional approval; it is not Human execution approval.
Producer acquisition preflight remains incomplete as recorded below. No dump
generation/import or prototype execution has started.

Subsequent execution status: the Human approved the spike, then requested a stop
at native acquisition preflight before review. See the
[preflight review](v06x-dump-acquisition-review.md) for its receipts and the
separately preserved work performed before that stop. The proposal below retains
its original decision context; it is not the current execution-status record.

Current status: acquisition evidence is accepted for the observed hosts;
bounded producer preflight passed on353bf92 inCI40173427178 for Ubuntu x86_64.
See the [saved producer receipt](v06x-dump-producer-preflight.md). Application
dump/comparison and import remain stopped, with resumption a separate Human
decision. No main integration, Qualification or release is performed here.

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

### Same application, extended input

Reuse the authored application in
[`tests/preparation_migration_acceptance/`](../../tests/preparation_migration_acceptance/),
as required by the [prior condition](v06x-preparation-import-design.md#human-review).
Apply its unchanged `m1_initial` -> `m2_addresses` revisions and successful seed
to native `app`: users `(1,'legacy',0)`, `(2,'seed',5)`, address
`(1,2,'seed@example.test')`, and `alembic_version='m2_addresses'`. Preserve their
columns, unique constraints and FK; do not replace this corpus or change the
existing migration acceptance owner. The spike adds a separate test-only
extension after the original preparation, with a manifest of its SQL and seed:

- Add `user_import_values`, an InnoDB table with a primary key, an explicitly
  named FK to `users.id`, `DECIMAL(20,6)`, nullable text and `VARBINARY` columns.
  Keep the two original users/one address unchanged. Added rows cover positive
  and negative exact decimal strings, SQL NULL versus empty string/bytes,
  Unicode, quotes, backslashes, semicolons and bytes including 00/27/3B/5C/FF.
  Record the exact expected values and hashes before dump production.
- Add one read-only procedure returning this user's imported values and one
  deterministic function computing a user's rating plus an argument. Use
  compound BEGIN/END bodies with multiple internal semicolons. Assert exact
  results, drain procedure results, and run a subsequent SELECT.
- Keep original child checks: the first commits user3; the second sees only
  users1/2 and the original address and rejects an invalid FK. Also check the
  extension's exact rows and routine results in both children.

Views and triggers are explicitly deferred from this first corpus. Pass
`--triggers` but assert zero source triggers/views; this tests neither feature.
The final recommendation must name both exclusions. Packages and events remain
outside the existing product scope. This extension establishes no arbitrary
legacy-app or MySQL-produced-dump compatibility.

### DEFINER and SQL SECURITY

Fix both routines to `DEFINER='root'@'localhost' SQL SECURITY DEFINER` on the
producer. Use the existing native root account on producer/reference; confirm
its existence before routine creation. Preserve DEFINER and SQL SECURITY in the
original dump and in all three imports, and compare their metadata exactly.
Do not use `--skip-definer`, rewrite clauses or create guest accounts. This
chooses an aligned producer definer, not normalization. The
[adopted routine contract](../decisions/routine-support-scope.md#definer-syntax-and-persistence-not-grant-enforcement)
already accepts explicit definers without enforcing account existence under
guest skip-grant-tables. It does not establish security-context equivalence.
Do not use CURRENT_USER/privilege-sensitive routine behavior as an equality
oracle. If this exact policy fails, report the blocker; do not remove routines.

### Producer options and comparison policy

Produce one canonical dump with the Ubuntu x86_64 identified12.3.3 producer;
transfer its bytes unchanged to both OS matrices. Do not produce a replacement
dump per route or OS. The fixed command profile is:

```sh
mariadb-dump --no-defaults --protocol=tcp --host=127.0.0.1 --port=PORT --user=root \
  --opt --single-transaction --skip-lock-tables --skip-add-locks \
  --routines --triggers --skip-events --hex-blob \
  --default-character-set=utf8mb4 --tz-utc --order-by-primary \
  --skip-dump-date app
```

PORT is a recorded test endpoint; authentication is supplied separately without
logging secrets. No `--databases`, `--all-databases`, `--compact`, `--compatible`,
`--force` or `--skip-definer`. Capture the pinned binary's version and help and
validate every option before producing data. `--skip-definer` availability is
not assumed or required: the selected policy retains the clause. Unsupported
selected options stop preflight; do not silently change this profile. Official
[option documentation](https://mariadb.com/docs/server/clients-and-utilities/backup-restore-and-import-clients/mariadb-dump)
is background; the exact12.3.3 help and observed output own this spike's format.

Set producer schema/table text charset/collation to `utf8mb4/utf8mb4_unicode_ci`,
session TIME_ZONE to `+00:00` and SQL_MODE to
`STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION` before
creating/seeding the app. Record the full native configuration and routine
creation context. Each destination precreates empty `app` with the same charset
and collation and selects it explicitly. Do not strip emitted session SQL or
executable comments; inventory actual directives before defining the reader.

Comparison normalization applies to collected observations only, never dump
bytes. Fix these rules before execution:

| Item | Classification and oracle |
| --- | --- |
| Tables/columns/constraints, engine and charset/collation | Compare exact semantic metadata, names, types, defaults, nullability, indexes and FK targets/actions; sort metadata collections by identity, retaining column/index member order. Do not rewrite engines/collations or rename constraints. |
| AUTO_INCREMENT | Compare column attribute and next counter against the clean native import before child mutations; no counter normalization. |
| TIME_ZONE and SQL_MODE | Execute emitted save/set/restore statements; compare session values before/after import and routine creation SQL_MODE. Normalize SQL_MODE only as a sorted set of flags. |
| CREATE DATABASE / USE | Precreate/select app explicitly; no --databases, so no CREATE DATABASE is requested. Preserve/execute any emitted USE app and compare selected schema. Unexpected CREATE DATABASE or another schema target stops format closure rather than being discarded. |
| LOCK TABLES | Excluded by skip-add-locks; skip-lock-tables concerns producer locking. Unexpected emitted locks stop format closure, not silent skip. |
| FOREIGN_KEY_CHECKS / UNIQUE_CHECKS / SQL_NOTES | Execute and restore all emitted settings; compare session entry/exit values and explicitly test FK/unique enforcement afterward. Do not infer enforcement from a restored flag alone. |
| Table/FK/statement order | Preserve exact dump execution order. Normalize only observation collection order; verify FK metadata and behavior. |
| Rows | Compare sorted primary-key rows with exact Decimal strings, NULL distinctions, Unicode code points and binary hex; no value normalization. |
| Routine definitions/behavior | Compare bodies, DEFINER, SQL SECURITY, creation charset/collation and SQL_MODE, plus exact results; compare observed definitions structurally, without broad text substitution. |
| Volatile observations | Ignore only routine CREATED/LAST_ALTERED times, table CREATE_TIME/UPDATE_TIME/CHECK_TIME, row-count estimates and physical allocation statistics in cross-engine equality; retain raw values. No other metadata exclusions without a recorded design decision. |
| Dump comments | Preserve bytes, including executable/version comments and sandbox directive. Ordinary comment timestamps/host text are not a SQL equivalence oracle; retain them in the original artifact. |

### Native acquisition preflight — incomplete, execution blocked

The acquisition routes are fixed below. Availability of a formula or an old CI
receipt is not a receipt for installed/runnable12.3.3 binaries in this spike.

| Platform | Acquisition route and current evidence | Required before dump/prototype execution |
| --- | --- | --- |
| macOS15+ arm64 | [Homebrew mariadb@12.3](https://formulae.brew.sh/formula/mariadb@12.3) lists12.3.3 and Apple Silicon bottles (checked2026-10-25). Standard local Cellar/opt paths checked here have no installation. | Pin the formula commit and matching OS bottle URL/SHA256 plus dependency receipts; acquire into the approved disposable workspace, identify/hash Mach-O arm64 mariadbd, mariadb and mariadb-dump, capture version/help, and verify temporary native server startup/query. No brew service or shared data directory. |
| Ubuntu24.04 x86_64 | Reuse the acquisition route in [.github/workflows/prepared-canonical.yml](../../.github/workflows/prepared-canonical.yml): mariadb@sha256:805c8e104bd563d5bfa24fadd3f31cd419ea859cb5277f32b5dbf2db714f9ed1. Existing receipts report12.3.3-MariaDB-ubu2404. | Resolve and retain the linux/amd64 child manifest digest, run on actual Ubuntu x86_64, hash the three executables, capture version/help and verify server startup/query. The index pin and prior receipt alone do not close this condition. |

Read-only local image inspection on2026-10-25 found that index pin cached as
**linux/arm64**, image ID
`sha256:23ccfa2f2df26837c8f397a8f9a070ad728768c095d246edd07cd8d24e9ec40c`.
This Linux VM image is neither a macOS native receipt nor an Ubuntu x86_64 one.
Neither native toolchain preflight is closed by this design update. After Human
approval, acquisition/version/hash/startup checks are the first bounded work;
if either platform cannot be acquired, stop before dump generation or reader
execution, return missing-input evidence and a concrete next step/cost estimate.
No substitution with an unrecorded version, emulated platform or Linux-only
matrix is authorized. Installation/build budget must be fixed before acquisition.

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
