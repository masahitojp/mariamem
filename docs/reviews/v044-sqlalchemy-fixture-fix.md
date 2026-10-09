# v0.4.4 SQLAlchemy consumer fixture repair

Release run [37918195197](https://github.com/masahitojp/mariamem/actions/runs/37918195197)
used final source `182bb716af21fd756b74e5f7aff637c1903d434e` and authenticated
runtime basis `c5f43106a8054bb59a2da9184a1c2103fe1a1d9f`.
The preceding regeneration repair succeeded: generated-Go reproduction,
two independent source-to-WASM builds and offline GPL source closure passed.
No publication occurred.

Both macOS and Ubuntu stopped at the first Fork-mode SQLAlchemy setup.
The fixture accessed `snapshot.path`, removed from the public API in v0.4.4.
All 11 cases errored during setup before SQL test bodies ran. This is not
an observed SQL/runtime failure. The earlier Fresh-mode SQLAlchemy cases passed.
[Compact evidence](v044-sqlalchemy-fixture-failure.json) records input identity,
artifact log/report hashes, completed stages and the failure location.

The repair deletes only `saved = snapshot.path` and `assert not saved.exists()`.
Consumer setup, Snapshot context ownership, disconnection, process reaping and
all SQL assertions remain unchanged. Owned backing/FD/storage cleanup remains
covered by accepted both-platform lifecycle evidence; external ORM consumers
must not depend on the private storage path. No runtime code changes.

Runtime reuse permits this precise deletion by comparing the entire module AST
against the accepted source. Arbitrary harness changes are not exempted. Tests
reject altered setup, yield, cleanup or unrelated assertions, and exercise the
actual fixture without a public path on normal completion, Close and exceptions.
Synthetic Git tests check both development scope and release fail-closed behavior.

Focused release preparation checks: 200 pytest cases (plus 6 subtests), 6 Product
tooling tests, version, generated-source inventory, public-source and diff checks
passed. Runtime acceptance and performance were not repeated locally. The fresh
final-artifact SQLAlchemy 44-case release gate is still required; this repair does
not substitute for that gate or claim it has passed. No automatic redispatch.

Reproduce: run `python scripts/release_preparation_checks.py` with pytest/PyMySQL.
For the committed clean source, run `python scripts/runtime_validation.py
--candidate-sha <exact-commit>` to authenticate both pinned Product artifacts.
