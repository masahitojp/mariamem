# Connection routing spike — local evidence, native CI pending

2026-10-24. The Human approved the [bounded design](v06x-connection-routing-design.md)
following design commit `dfa6b21c4b4fb2c6e5e7e5db0d21eeef52394776`.
Branch: `experiment/connection-routing`. No production API/runtime change.

## Current conclusion and next gate

**The spike is not complete.** Local real-guest evidence supports PyMySQL routing,
SQLAlchemy pool-generation checks and Go child-owned pools. Twelve local cases
pass and four deliberate defects are detected. Required Connector/Python routing
is SKIP because its import fails under this Homebrew Python/OpenSSL build;
Ubuntu has not run. Native CI must supply these missing results before the
post-spike Human Review can choose production work or a narrower implementation.

Recommendation now: execute the committed bounded matrix on macOS15 arm64 and
Ubuntu24.04 x86_64 with CI's Python3.14 distribution. This is the approved spike's
remaining verification, not an additional compatibility campaign. The strongest
objection to the routing approach remains hidden use of old connections: the
negative controls reproduce that exact mistake, while the prototype prevents it
within the explicitly enrolled path. They do not establish coverage of arbitrary
raw handles, custom creators or Connector's built-in pools.

## Fixed inputs and ownership

- Runtime source_commit: `dfa6b21c4b4fb2c6e5e7e5db0d21eeef52394776`, a clean
  commit verified by `scripts/git_identity.py`; runtime is identical to adopted
  main `9f29194bbddd6a9431a4a250bd2f93ee813734af` (the intervening change is design
  documentation only). Go binary metadata has that commit and modified=false.
- Go1.26.10; guest SHA256
  `8f6177627855232d096cfb3987d94e35c19fc4fc0c7f32ca8c69ff9fd4990a40`.
  Local host SHA256
  `ba0b4ec65dfabbcd601917c509f8453fe48bf1ecdffc642a6fefad89c18df3f0`.
- macOS27.0.1 arm64; Homebrew Python3.14.8 / OpenSSL4.0.3.
  PyMySQL1.2.3, SQLAlchemy2.0.54, Connector/Python26.7.0;
  Go driver1.9.3. Installed package sources/wheel hashes and actual prototype
  file hashes are in [inputs.json](v06x-connection-routing-evidence/macos-local/inputs.json)
  and [dependencies.json](v06x-connection-routing-evidence/macos-local/dependencies.json).
- Authored prototype only:
  [router.py](../../tests/spikes/connection_routing/router.py),
  [campaign.py](../../tests/spikes/connection_routing/campaign.py),
  [Go client](../../tests/spikes/connection_routing/go_consumer.go),
  [runner](../../tests/spikes/connection_routing/run.py).
  The guest, canonical/generated owners, converter patches, release guards and
  accepted consumer exception decision are unchanged. No independent generation
  claim is made: an unchanged canonical host was compiled for the experiment.

## Matrix — local macOS

[Original outcomes and details](v06x-connection-routing-evidence/macos-local/control.json).
R7 is partial; counting its Go result does not close its Python requirement.

| Row | Local outcome | Observed boundary |
| --- | --- | --- |
| R1 | PASS | Direct and saved PyMySQL class alias, object constructed before hook installation with deferred connection, reconnect: all markers A |
| R2 | PASS | Cold engine / held-idle diagnostic reuses the same pool across A/B/A; markers A/B/A; two generation invalidations in that case |
| R3 | PASS | Active checkout/transaction enrollment rejected; custom creator rejected before it runs; unregistered profile rejected |
| R4 | PASS (3 cases) | Two threads query/write A/B independently; nested A/B/A; explicit context propagation works and missing thread context rejects; asyncio task contexts keep A/B (synchronous DBAPI, not async-driver coverage) |
| R5 | PASS (3 cases) | Retired copied context and missing target reject; setup/test failures survive cleanup; injected cleanup error is attached; nested outer scope restored; closed child rejected |
| R6 | PASS for executed PyMySQL cases | Socket/option-file conflict and explicit TLS reject; named `app` schema, qualified SQL, utf8mb4, autocommit=false and rollback preserved. Connector option check is not executed while import is unavailable |
| R7 | Go PASS; Python SKIP | Go separate pools use explicit DB/Tx/Conn Prepare, parameterized non-interpolated execution, commit/rollback and correct markers; Connector default/pure/C could not import locally |
| R8 | PASS | Prepare once, capture, independent children via explicit injection and routing; child commits remain independent; teardown completes |

Control sentinel connection attempts: **0**. All started hosts reaped.
`control.passed=false` and runner `complete=false` intentionally retain the Python
SKIP. The local flag `--allow-connector-import-skip` permits collecting the rest
without presenting complete acceptance. CI does not use that flag.

R2 deliberately keeps an idle physical connection alive after retiring its scope
(`cleanup=False`) to isolate the generation-check oracle. Ordinary scopes close
owned resources. The final control run has no pool double-close warnings after
teardown was changed to invalidate enrolled pool records through SQLAlchemy.
This is a prototype repair, not a guest/lifecycle-contract change.

## Deliberate defects and user impact

| Injected defect | Actual observation | Oracle |
| --- | --- | --- |
| Remove pool-generation check | Intended A/B/A instead reads A/A/A: the second test uses the first test's DB | R2 assertion fails |
| Allow missing-target fallback | One connection reaches the controlled original endpoint | R5 listener sees attempt; connection fails |
| Ignore retired scope | A copied context can connect after scope exit while the child still exists | R5 expected rejection fails |
| Use one global target | Both workers read B in the observed run; A's expected marker fails | R4 assertion fails |

All four campaigns exited1 for the intended case, not a setup/import/fatal
error, and reaped their hosts. Raw outcomes are in the adjacent mutation JSON/log
files. These controls show why routing needs scope and pool checks; the original
destination was a local listener, never a production DB. They are not observations
of defects in released mariamem, which has no such routing feature.

## Environment finding and repaired prototype issue

Connector's Python-source digest is
`7945eab736effa50c861b2b7200a1e8bee35cf85af9009105baa0993df6c7c56`, identical
to the P6 Mac/Ubuntu environment receipts. Here its `network.py` accesses
`ssl.PROTOCOL_TLSv1`, absent in Homebrew Python3.14.8 linked to OpenSSL4.0.3.
It fails before reaching any DB. Prior P6 Mac CI used Python3.14.7/OpenSSL3.5.7;
Ubuntu used Python3.14.9/OpenSSL3.0.13. Package-version equality alone does not
establish importability. No SSL monkeypatch, driver edit or downgrade was used.
The cause beyond this missing-constant boundary was not investigated here.

The first local prototype also wrongly treated PyMySQL's default PREFERRED TLS
as required TLS, rejecting ordinary connections. Pinned PyMySQL
`connections.py:277–309` distinguishes `_ssl_required` from `ssl`; the prototype
now preserves the driver's default and rejects explicit required TLS. The
[initial failure record](v06x-connection-routing-evidence/macos-local/initial-tls-rejection.json)
is retained, and the final R1–R8 outcomes use the repaired prototype. No TLS
option was dropped merely to get a PASS.

## Limits and remaining decision material

- One logical TCP endpoint/profile is enrolled. Separate unregistered connections
  remain outside interception; arbitrary custom/native handles are not contained.
- The saved ordinary Connector factory enters a shared abstract connect method,
  but option-file/DNS/failover/built-in-pool processing occurs earlier in its
  factory. Only the enrolled module entry rejects these options proactively;
  saved factory aliases with those advanced options are **not established safe**.
  Required default/prepared direct connection remains in R7; advanced factory
  coverage is a productization design boundary, not implicitly claimed.
- SQLAlchemy registration uses a pinned default-creator/private introspection
  seam and QueuePool. This needs maintained version checks before production.
  Enrollment assumes application tasks are quiescent: checked-out counts are
  not an atomic barrier against a concurrent new checkout. Existing checked-out
  raw handles cannot be discovered globally or moved.
- Parallel cases use a finite number of cooperative tasks. Reconnect counts are
  diagnostics, not a throughput benchmark or fairness/forced-stop guarantee.
- Go is a real driver consumer of child endpoints hosted in the Python-managed
  Go host; it demonstrates child-owned pools, not transparent replacement of an
  arbitrary pre-existing Go application pool. GORM adapter UX is still design work.
- The ordinary prepared SELECT/write/rollback/commit composition is tested by R7
  when runnable. Accepted Oracle CALL/NUL exceptions are not reclassified or
  overridden; the unchanged P6 decision/evidence remains their owner.
- R8 records a small hand-authored schema/seed flow. It does not satisfy the
  separate Django/Alembic, dump import or broad first-test UX workstream.
- No production API, published support expansion, main integration,
  Qualification, Product Validation or release is requested by this checkpoint.

## Reproduction and evidence retention

Use two clean checkouts: runtime at the fixed source above and this prototype
revision. Create a Python3.14 virtualenv, then:

```sh
python -m pip install --report dependencies.json -r tests/spikes/connection_routing/requirements.txt
python scripts/experiment_disk.py --work-dir /absolute/disposable/routing --min-free-gib 8 --budget-gib 8 --timeout 2400 -- python tests/spikes/connection_routing/run.py --runtime-root /absolute/runtime-checkout --output /absolute/disposable/routing
```

The runner verifies runtime commit/clean state/guest identity and compiled host
buildinfo; records package and prototype hashes; runs the control and four
mutations; requires expected failure location plus cleanup for each mutation.
No release-sized guest rebuild is needed for these authored helper changes.
[CI workflow](../../.github/workflows/connection-routing-spike.yml) checks out
runtime and prototype separately and runs this same matrix on both supported OSes.
CI result collection and the final Human recommendation remain pending.

Saved [files.json](v06x-connection-routing-evidence/macos-local/files.json)
distinguishes original and stored SHA256: absolute checkout paths become
`<repo>`, log extensions become `.txt`, and host buildinfo trailing whitespace
is removed. Hashes inside the original runner receipt refer to its original files.
Compact logs/JSON and prototype source are retained; the disposable host,
compiler/module caches and venv are removed after preservation. This checkpoint
must not be used as a completed-spike or production-adoption receipt.
