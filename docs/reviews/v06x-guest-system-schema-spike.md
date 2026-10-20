# Stored routine system-schema feasibility — Human Review

2026-10-20. **Minimum WASIX procedure/function feasibility: PASS. Recommend a
bounded minimum-bootstrap design if the Human elects to add routines to the
product scope.** The unchanged experimental guest executes all six native-control
cases after creating `mysql` and the official `mysql.proc` table. No MariaDB
internal API extension, new Wasm code, converter patch or generated-Go edit was
needed. This resolves the practical question “can this guest execute routines?”
positively; it does not approve production implementation or choose its version.

The strongest objection to adoption now is that these are **post-ready SQL
experiments**, not a production bootstrap with lifecycle/failure contracts and
both supported OSes verified. Also, the complete upstream upgrade script has an
actual embedded incompatibility. Those findings favor a small routine-specific
bootstrap over blindly running install/upgrade SQL at every Start; they do not
justify shipping this probe. Decide the routine scope/version and initialization
owner in Human Review. Prepared/multi-statement v0.6.0 scope stays unchanged.

## Basis and exact inputs

Basis: [prepared/multi spike](v06x-prepared-multi-spike.md) at
`866c17e7c64c7b0bee73b3e5b42a1b83982d4378`, its
[design](v06x-prepared-design.md), main scope decision
`de0e08a9c4248969a7522abebfdee8aea6ef9657`, and the
[Snapshot contract](../decisions/snapshot-product-contract.md).
Branch: `experiment/guest-system-schema`, starting at that report commit.
The original guest/host sources remain `926365bdc853bd2a45cc00139db1b64c5d78e3e9`
and `7037f05bb279de4ce7aab622e33b13e20d7c52f0`; this fresh source build and host
generation ran at **`866c17e7c64c7b0bee73b3e5b42a1b83982d4378`** before adding
this report and probes. Do not substitute a later report SHA for tested source.

| Input/artifact | Identity |
| --- | --- |
| MariaDB source | `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`, 12.3.3; archive SHA256 `36319b89c4373cf35e5c5c08686625eccae2816257b6982a4815ff552b945845` |
| lite4mariadb | `24be9371a2f6c71250a2356631ad6feab2280b02` |
| goccy wasm2go | `730057c146463f663e8774587bc96fb2bea91af8` + the existing 13 patches, unchanged |
| Fresh Wasm | `55c5d4910459c87b5e1e00eb999506acc661ea0eaa3a794662db647bd124c953`, 18,436,818 bytes; identical to prior spike |
| Fresh host binary | `f779d6a4e092c9dddbc9a27b7f225cf8466031105c6ce3dc7b7ef2efe7a44b89`, 100,154,994 bytes; identical to prior tested binary |
| Native control | `mariadb@sha256:805c8e104bd563d5bfa24fadd3f31cd419ea859cb5277f32b5dbf2db714f9ed1`, Linux arm64; `version_source_revision` equals the MariaDB commit above |
| Toolchain | Go 1.26.8; LLVM 23.1.0, WASIXCC 0.4.7, sysroot 2026-07-03.1 legacy EH, Binaryen 133; exact archives/options in guest record |

The [evidence index](v06x-guest-system-schema-spike-evidence/files.json) records
original/stored bytes and SHA256, including lossless gzip where used. Important
records are `git-input-identities.json`, `fixed-patch-identities.json`,
`guest-record.json`, `translation.json`, `installation-inputs.json`,
`provenance.json`, `development.json` and `native-source-revision.json`.
All three upstream identifiers were verified as **commit objects** with
`scripts/git_identity.py`, not inferred from their spelling or tag rows.

## Results and finite oracles

The [machine assessment](v06x-guest-system-schema-spike-evidence/assessment.json)
is derived from unmodified raw query outcomes by the retained `assess.py`.
`probe.py` uses PyMySQL 1.2.3 on Python 3.14.8; Connector/Python is not imported.
Go diagnostics use go-sql-driver/mysql 1.9.3. No claim about prepared CALL follows.

| Check | Result | Evidence / limit |
| --- | --- | --- |
| Empty guest: direct CREATE PROCEDURE, ROUTINES/PARAMETERS | Expected 1146 reproduced | `guest-baseline.json`: only information_schema/test; mysql unknown1049; USERS count0. Raw routine cases remain FAIL1146, not rewritten |
| Official proc DDL only | PASS, 6/6 native parity | `guest-proc-only.json`, `native-final-baseline.json` |
| Complete official base script | PASS, 89/89 statements; routines 6/6 | `guest-base-fix.json`, base stage |
| Complete official fix script | **FAIL under upstream upgrade policy** | 242 statements; 87 raw failures, 86 in upstream expected-error set, one unexpected1193; below |
| Routines after fix attempt | PASS, 6/6 | Does **not** turn the failed full-fix path into PASS |
| Controlled definition mismatch and repair | Negative oracle + recovery PASS | Direct CREATE returns1728; log names comment/ordinal15/NOT NULL; restoring definition restores 6/6 |
| CREATE EVENT before/after schema creation | Unsupported boundary confirmed1235 | All guest conditions; native CREATE accepted. Event scheduling itself not tested or implemented |
| Fresh source build / normal generation / compilation | PASS, UNQUALIFIED | Guest and host hashes match the reviewed experiment |
| Independent regeneration comparison | PASS for identical runtime | Fresh raw module52 files equal both earlier independent inventories; installed98 runtime files equal prior, provenance differs with actual source/path record |
| Official development smoke | PASS | SQL/transaction/Snapshot/three Forks/shared-host cleanup, ordinary DB state; not routine persistence across Fork |
| Source-origin and lifetime-binding mutation tests | PASS,34 | `input-boundary-tests.log`; no oracle/guard changes |
| Historical Web REPL1728 exact cause | SKIP / unconfirmed | Exact manual DDL, error log and deployed build identity unavailable; controlled experiment is not historical attribution |
| Deployed Emscripten/WASIX equivalence | SKIP | Fixed lite4 source comparison below, no deployed REPL provenance |
| Native Ubuntu x86_64 / embedded-SQL build costs / full Qualification | SKIP | Not executed in this macOS arm64 SQL-only experiment |

Six cases: CREATE/CALL/DROP procedure; IN/OUT/INOUT (`6,13`); function invocation
including NULL (`5,NULL`); two result sets (`7`, `8`) plus terminal OK and
MORE_RESULTS `[8,8,0]`; ROUTINES/PARAMETERS metadata while a routine exists;
SIGNAL1644 after a returned row, subsequent SELECT reuse, and1305 after DROP.
The parity oracle compares the actual values/result sets/codes to native.

## What 1728 establishes, and what it does not

The exact official DDL at
[mariadb_system_tables.sql:151](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/scripts/mariadb_system_tables.sql#L151)
**does not reproduce1728** in this WASIX guest. It is sufficient for the minimum
cases with `CREATE DATABASE mysql; USE mysql; SET sql_mode=''` and Aria available.
The probe also sets `@auth_root_socket=NULL` as bootstrap context; that variable
is not used by the proc DDL. No global-privilege rows or procs_priv table were
needed for these minimum cases under the existing skip-grant-tables mode.
This is not a general privilege/DEFINER compatibility result.

To verify the detector, the isolated empty proc table was deliberately changed:
`ALTER TABLE mysql.proc MODIFY comment text COLLATE utf8mb3_bin NULL`.
Direct CREATE then returned1728 and the guest log reported:

> expected column 'comment' at position 15 to be NOT NULL

Changing the same column back to NOT NULL restored every case. Native reproduced
the same error and recovery. Thus1728 can mean **incompatible table definition**,
not necessarily damaged stored bytes. The original Web REPL manual DDL was not
provided, so this is not evidence that its particular mismatch was comment.
No open-ended REPL investigation is needed to establish current WASIX feasibility.

Source checks: [sp.cc:120-246](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/sp.cc#L120)
defines22 expected fields; [table.cc:5689-5840](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/table.cc#L5689)
checks count/version, type prefix, charset prefix and NULL flag. Name prefix
mismatches are logged but are not fatal by themselves; ordinal positions are
used. Charset expectation is prefix `utf8mb`; the official DDL explicitly uses
utf8mb3. ENUM/SET prefix matching permits appended PACKAGE values; it is not
itself the mismatch. Procedure/function/CALL dispatch has no event-style embedded
prohibition; events are disabled by HAVE_EVENT_SCHEDULER.

`mysql_version` here is the FRM creation-version metadata read at table.cc:1990,
not an arbitrary SQL user variable. The actual generated
`built-mysql-version.h.txt` records `MYSQL_VERSION_ID=120303`. Matching source and
DDL creates the table with this server; no fabricated version variable was set.

## Official initialization: necessary subset versus whole installer

Actual new install at
[mysql_install_db.sh:580-605](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/scripts/mysql_install_db.sh#L580)
uses base + performance + data + help + GIS + sys scripts through bootstrap.
`mariadb_system_tables_fix.sql` is an **upgrade** script, not the second half of
new install. This experiment executed the requested base/fix pair, not that whole
new-install ceremony. It did not populate accounts/help/time-zone data or claim
install-db completeness. The fixed-script parser handles client DELIMITER syntax;
it does not rewrite SQL statements or implement a product dump importer.

Base89 statements all succeeded on an empty guest. The fix stage continues after
each error **only to collect this experiment's evidence**. Every raw failure is
retained. The source-bound ten-code allowlist in
[mysql_upgrade.c:1057-1089](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/client/mysql_upgrade.c#L1057)
explains86 of87 guest failures. Statement171 (zero-based170), official
[fix.sql:689](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/scripts/mariadb_system_tables_fix.sql#L689),
`set global event_scheduler=original`, fails1193 because the embedded server has
no such variable. **1193 is not allowed by that source policy.** Nothing was
removed, patched or newly allowlisted to conceal it. Native's87 raw errors are
all on its expected list; its starting system schema was already installed,
unlike the guest. See `upstream-upgrade-error-policy.json` and raw JSON.

This blocks the claim “use the entire upgrade script unchanged as bootstrap.”
It does not block the demonstrated minimal routine path or justify adding events.

Fixed lite4 source VERSION is13.1.0, while adopted server source is12.3.3.
The proc DDL and compiled proc-field-definition block are byte-identical between
those two source archives (`lite-vs-adopted-proc-definition.json`). The linked
Wasm/host and the deployed Emscripten REPL are not interchangeable identities;
the latter has no verified deployment receipt here.

## Diagnostic costs — macOS arm64, not performance acceptance

Unchanged Wasm size increment: **0 bytes**. Both source rebuild and host binary
match the previous spike exactly. SQL payloads were supplied at runtime; a future
embedded-SQL code/data size increment was **not measured**.

Each separate-process cohort starts three independent empty DBs, not reused
tables. “Cold” below means first Start in that process; OS caches were **not**
flushed. “Later” is the median of its two subsequent Starts. SQL runs **after**
ready, through one ordinary connection. Start times are recorded separately;
their variation cannot be attributed to initialization that has not run yet.

| Path | First Start | Later Start | First SQL initialization | Later SQL initialization |
| --- | ---: | ---: | ---: | ---: |
| Control | 42.8ms | 36.1ms | ~0 | ~0 |
| Setup + proc DDL, five statements | 51.2ms | 44.0ms | 2.7ms | 2.3ms |
| Setup + base/fix observation path | 52.7ms | 36.2ms | 137.8ms | 125.2ms |

The full path above still contains1193 and is not a valid production bootstrap.
An additional alternating-order cohort (three DBs per path) measured initialization
medians proc1.34ms and base/fix131.36ms. These small diagnostics support an
order-of-magnitude distinction, not precise regression/latency promises or a
causal comparison of complete test-suite times. Raw timings, errors and procedure
sanity checks are in `cost-*.json`; post-ready SQL is not an integrated ready-gate
measurement. No cold filesystem/storage claim follows.

For v0.7 initialization work: loading all upgrade work at every Start would add
avoidable work; minimum routine setup is much smaller here. Whether a bootstrap
belongs only in Fresh, is reused from a prepared baseline, or runs conditionally
requires the product/lifecycle design. No new Fork optimization is proved.

## Change ownership, remaining production scope and stop

This spike adds only authored experiment probes, report and evidence. Against
the `866c17e` basis: **no guest/experimental.patch changes, no authored guest overlay
changes, no canonical guest/source.patch changes, no converter changes, no
production runtime changes**. Existing prepared experimental changes remain
experimental. Generated Go was created by the normal development route, never
edited. The disposable Go cost probe was added under tests only after that route
finished its inventory checks. Runtime99-file inventory was checked again;
98 runtime files and the host binary exactly match previous evidence. New
provenance retains actual input paths/source866c17e, rather than being normalized
to claim99-file equality. The previous independent52/99-file evidence remains
linked in the prepared report; this fresh52-file raw module matches both of its
independent inventories. Existing J1 function bytes, bindings and failure oracle
remain unchanged; no new general shared-memory conclusion is made.

If the Human chooses productization, budget separate work packages:

1. Define the **minimum routine bootstrap contract** and guest/upstream owner:
   pinned DDL/version identity, exactly-once timing before ready, connection state
   restoration (database/charset/sql_mode), explicit failure propagation and
   treatment of upgraded tables. Do not silently catch1193 or seed a fake version.
2. Implement only that approved initialization at its owning source; promote the
   smallest canonical patch if needed, rebase/maintain it with MariaDB updates,
   regenerate through existing ownership/identity guards. Full account management,
   events, sys/help installation and prepared CALL remain separate scope choices.
3. Verify seeded routine persistence/isolation through Snapshot/Fork, concurrent
   calls/teardown, relevant driver paths, SQL SECURITY/DEFINER expectations and
   both supported OSes. These probes are explicitly selected experiments, not
   main CI coverage; move approved regression cases into the adoption gates.
   Update support/import diagnostics and documentation.
   Current ordinary Snapshot smoke does not cover seeded routines. Qualification
   and release remain subsequent decisions, not included in this estimate.

The source recipe already contains routine code, so the minimum path is an
initialization change, not evidence of a need to replace the engine or extend
internal MariaDB APIs. These packages are a scope estimate, not implementation
approval or a promised schedule. No production edits, main merge, Qualification,
tag or release occurred. Unrelated main untracked `glow` and `god` are preserved.

Reproduction, exact commands and cleanup are in
[reproduce.md](v06x-guest-system-schema-spike-evidence/reproduce.md).
