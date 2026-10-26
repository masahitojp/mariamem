# W3 — standard Django runner lifecycle discovery

This bounded experiment uses stable main bf3a29c and the exact W4 orders app,
two migrations and migration seed, with no dependency on the pending Live
candidate. The Human approved investigation and native/mariamem comparison;
there is no new product adapter, routing hook, Django backend or runtime patch.
`input-manifest.json` fixes versions, native image, app hashes, resource budget,
mandatory platforms and the local observation boundary before execution.

## Questions and deterministic observations

Each Python interpreter runs ten suites against native MariaDB, the ordinary
guest endpoint, and each of two independent baseline-copy campaigns. Each suite
has two actual tests. Framework-owned test DB creation, migrations and teardown
remain in control. Explicit settings select a unique disposable original schema
and test schema; an original-schema sentinel must stay unchanged. Querying
`DATABASE()` and the two migration records prevents original-target fallback.

- `TestCase`: `setUpTestData`, per-test/class atomic rollback, in-process HTTP,
  savepoint recovery after exact duplicate errno1062 and refusal of explicit
  commit inside its atomic wrapper. Repeat in reverse order.
- `TransactionTestCase` / `transaction=True`: real committed writes, on_commit
  execution and visibility from a separate physical connection.
- `serialized_rollback=True`: restore migration seed before both tests. Repeat
  Django's serialized cases in reverse order.
- Default transactional flush: observe seed in the first test and an empty
  application table in the second; do not silently restore seed or claim that
  flush replays a data migration.
- Intentional failure after a committed write: require the exact failure marker,
  second-test baseline restoration, correct nonzero exit and complete teardown.
  An unrelated error, skip or generic nonzero exit fails the parent assessment.

`observation.Runner` only records standard setup/result/teardown around super
calls. pytest-django uses its original fixtures, including `db` and standard
transaction/serialization markers, with no setup fixture override. It runs in a
separate explicitly configured process, with plugin autoload disabled and the
pinned pytest-django plugin explicitly loaded.

For Fork, a separate preparation process calls Django's standard test DB setup
and then exits. After its connections close, Snapshot consumes the source. Every
suite starts from its own Fork. The ordinary `--keepdb` / `--reuse-db` options
reuse the pre-migrated test schema inside that disposable child. Framework
rollback/flush still owns individual test isolation. **This is one Fork per
runner invocation, not one Fork per Django test.** The child is destroyed after
the suite; kept test schemas never persist across child owners or process runs.

## Reproduce

Install `requirements.txt` into a disposable Python3.11/3.14 venv. mysqlclient
requires the normal native development headers/pkg-config. Build
`cmd/mariamem-host` with Go1.26.10 from an exact clean checkout; run source
identity preflight with `scripts/git_identity.py inspect HEAD` before the build.
Acquire the exact manifest's native image/server and verify its version/image
binding before running. An unavailable native input stops comparison.

```sh
PYTHONPATH="$PWD/python" python tests/django_lifecycle/run.py \
  --native-port NATIVE_PORT --host build/mariamem-host \
  --expected-source-commit FULL_SOURCE_COMMIT --output build/django-w3/py311
```

Use a fresh output directory for each interpreter/source cohort. Tests are
opt-in and excluded from ordinary pytest collection. Guest execution starts only
after every native suite passes its declared oracle. A local emulated Linux
server does not prove a native macOS server or an Ubuntu host run. Both supported
host OSes remain mandatory before a product support/adoption claim. No runtime
performance, cold setup, parallel or arbitrary-project compatibility is implied.

## Source investigation and next decision

Inspect the installed pinned Django `testcases.py`, `runner.py`, database creation
and MySQL creation modules, plus pytest-django `fixtures.py` / `plugin.py`.
Record hashes and function locations with the raw observations. Compare the
standard settings route, runner-granularity Fork recipe and a potential lifecycle
adapter only after those observations exist. A public adapter, per-test Fork,
multiple aliases, async and parallel runners require their own design decision.

## Mixed-suite and migration-failure extension

run_mixed.py keeps the same original application hashes and package/native pins.
It adds four explicit class/group orders for each runner, standard per-test seed
fixtures where needed, and native/ordinary-guest/two independent Fork routes.
Django's own TestCase-first ordering remains authoritative for its --shuffle/
--reverse runs. The test-only pytest collection plugin keeps classes contiguous
while permuting groups and methods; it does not replace lifecycle fixtures.

An extra third migration reuses the original first two migration classes, creates
a marker table, then fails with missing-table errno1146. The observation must
retain original error chains and partial DDL, with zero admitted test bodies.
Fresh guest owners are discarded after each failure; a native test schema is
dropped explicitly by its parent after preserving the state. No failed source is
captured in a Snapshot. The minimal runnable settings/parent recipe in
docs/examples/django is checked both for normal mixed tests and that same setup
failure, including original process exit and host/temp cleanup.

Use the same run.py arguments with tests/django_lifecycle/run_mixed.py and a fresh
output directory. This extends the investigation; it does not rewrite original
92dc7fa receipts or claim Ubuntu, product adapter or release acceptance.
