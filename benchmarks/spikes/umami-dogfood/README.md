# Umami v2 MySQL dogfood — unmodified migration blocked

2026-11-05, macOS arm64. This is a bounded local dogfood report, not release
acceptance. Product, guest, SDK, version and CI are unchanged.

**Conclusion:** Umami v2.20.2 cannot install unmodified on this mariamem main.
Migration `05_add_visit_id` fails with Prisma P3018 / SQL1305:
`FUNCTION umami.BIN_TO_UUID does not exist`. Native MariaDB12.3.3 fails at the
same statement. This is a MySQL/MariaDB SQL compatibility boundary, not evidence
of a new Prisma wire/pipelining regression.

A diagnostic function on a new **empty** database unlocks further testing.
It does not establish that populated upgrades or full MySQL semantics work.
Recommend tracking the SQL compatibility gap before claiming Umami support;
do not add a heavy CI job or ship the diagnostic function as a product fix.

## Results (separate cohorts, original failures retained)

| Cohort | Result | Meaning |
| --- | --- | --- |
| Original 13-migration deploy | FAIL at05 | First04 finish; missing function blocks install |
| Native MariaDB original deploy | Same FAIL at05 | Independent native reference |
| Diagnostic fresh install | 13/13 PASS | Empty DB with test-only BIN_TO_UUID; repeat upstream check-db PASS |
| Real application query cases | 12/12 PASS | Upstream Prisma CRUD, event/session writes, aggregate/filter/timezone SQL, reset/delete |
| Original Cypress API, 3 specs | 25/25 PASS | Team10, user7, website8; zero skips/pending/retries |
| Original Cypress UI, 3 specs | 6/8 PASS, 2 FAIL | Blank-login Required text and user-role display |
| Native MariaDB diagnostic UI | 7/8 PASS, 1 FAIL | Same user-role display failure; blank-login PASS |
| Focused original login-spec recheck | 2/2 PASS | Fresh mariamem diagnostic DB; initial UI6/8 remains recorded |
| Original Jest | 18/18 PASS, 3 suites | Pure helper tests; not database acceptance |

For API, queries and UI, the prepared mariamem database was captured with
`Snapshot(max_forks=3)`, then each cohort used an independent sequential Fork.
The native UI comparison used native MariaDB directly, without Snapshot/Fork.
Each Cypress test had one attempt and retained upstream assertions/default
4-second assertion deadlines. No skipped tests or relaxed oracles count as PASS.

The role/password UI test expects `View only` but sees the old `User` row on
both backends. The original API user-update and subsequent read assertions
pass against mariamem. This does not establish a database persistence bug.
The blank-login failure was not reproduced by the focused recheck; timing is a
possible explanation, not a proven root cause. Neither result makes UI8/8 PASS.

The first diagnostic run stopped before UI because the harness immediately
reused a closing Next port. The runner now selects a fresh loopback port per
cohort. That harness failure was not an application test failure and remains
in local evidence; its completed query/API results are retained separately.

## Why adding one function is insufficient

Migration05 forms UUID bytes using `RANDOM_BYTES(16) & mask | mask` and then
calls BIN_TO_UUID. Native MariaDB's fixed-vector probe returned
`8000000000000000` plus a DECIMAL truncation warning. Full128-bit byte arithmetic
would produce `1234567890AB4DEF8011223344556677` (Python-computed expectation,
**not a native MySQL8 execution result**). See native-control.json.

[MySQL8 documents binary-string bitwise operations](https://dev.mysql.com/doc/refman/8.0/en/bit-functions.html),
whereas numeric evaluation is64-bit. A populated migration05/backfill needs an
explicit differential test; no native MySQL8 run was performed here.

`diagnostic-bin-to-uuid.sql` handles only a valid16-byte value, without the
optional swap flag or full invalid-input behavior. On the empty database the
migration UPDATE has no rows, so its UUID-generating expression is not qualified.
This bootstrap is neither a production workaround nor a proposed public API.

## Pinned inputs and execution

- mariamem source_commit: `c27061f1a33eed2908fd90b0e2d816692e001339`.
  Host built from a clean standalone shared clone using Go1.26.10,
  `go build -p 1 -trimpath -buildvcs=true`; runner verifies its Git build stamp.
- [Umami v2.20.2](https://github.com/umami-software/umami/tree/3eb2e890efb5b18bdfbeab46b9946f48e38da424),
  source_commit `3eb2e890efb5b18bdfbeab46b9946f48e38da424`.
  Lightweight tag: tag_object_sha is null. MySQL-capable v2 was chosen;
  this does not claim v3 support.
- inputs.json records archive SHA256; input-sha256.json records39 unchanged
  source inputs (schema/13migrations, package/lock, test fixtures/support/specs,
  query helpers). Checks verified those bytes after execution.
- Frozen pnpm9.15.9 install with lifecycle scripts disabled; explicit upstream
  build-db, build-tracker and build-geo. Prisma/client6.7.0, Next15.5.9,
  React19.2.3, Node24.22.1, Cypress13.17.0/Electron118.0.5993.159.
  Official GeoLite download used; URL and resulting digest in metadata.json.
- Next uses upstream dev-turbo / Turbopack on loopback, with unauthenticated GET
  route preparation. Preparation responses are not counted as tests.
  Original Prisma client/pool and original SQL/migration/test files are used.
- Native control: pre-existing mariadb:12.3 image (digest in
  native-image-digest.json), server12.3.3-MariaDB-ubu2404. Dedicated disposable
  containers/volumes were used, with no production database or credentials.

## Reproduce

Use the repository experiment-workspace workflow: 8GiB owned budget, 6GiB free
reserve, pinned source under `TASK_WORK/temp/host-source`, upstream under
`TASK_WORK/temp/umami`, stamped host `TASK_WORK/temp/mariamem-host` and Python
venv with mariamem source/PyMySQL. Install frozen dependencies in an owned store;
run upstream `build-db`, `build-tracker`, `build-geo`, and install pinned Cypress
in an owned `CYPRESS_CACHE_FOLDER`. Do not set hosted-service credentials.

Copy db-cases.ts to upstream `.mariamem-db.ts`, bundle with upstream esbuild
`--bundle --platform=node --packages=external --outfile=.mariamem-db.cjs`.
Copy cypress-run.cjs to upstream `.mariamem-cypress.cjs`. Run:

```sh
python benchmarks/spikes/umami-dogfood/run.py --workspace TASK_WORK \
  --output TASK_WORK/evidence/original
# Expected migration05 failure above. Separate diagnostic fresh DB:
python benchmarks/spikes/umami-dogfood/run.py --workspace TASK_WORK \
  --output TASK_WORK/evidence/diagnostic --diagnostic-compat
# Optional bounded login recheck, unchanged upstream spec:
python benchmarks/spikes/umami-dogfood/run.py --workspace TASK_WORK \
  --output TASK_WORK/evidence/login-recheck --diagnostic-compat \
  --cohorts ui --ui-spec cypress/e2e/login.cy.ts
```

A fresh native control can pass `--native-port PORT --diagnostic-compat
--cohorts ui`. It must start empty and is explicitly labelled native in results.
The harness closes Next and DB handles; the operator removes owned native
containers and browser caches after preserving evidence.

## Evidence and limits

Compact per-case JSON, input hashes, probe output and runner source are committed
alongside this report. Original logs and selected failure screenshots are retained
in the local workspace evidence; dependencies, source copies and caches are
disposable. Production build, tracker browser ingestion, historical populated
upgrades, native MySQL8, Ubuntu/installed artifact acceptance, performance/RSS
and Release qualification were not tested. No support promise follows from
conditional query/API success.
