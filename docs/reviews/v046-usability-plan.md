# v0.4.6 Product Usability & Validation — discovery and implementation plan

Status: implementation authorized on `experiment/v046-usability`, starting at
main `0fef33c752053d3bd1e180f9e46f4a301cfcd5eb`. The following design and
historical inputs are retained; current execution results belong to the v0.4.6
Human Review report. No main merge or release is authorized by this plan.

## Exact inputs

- Stable main: `8ede4ad65def07436b64801076004ff80aec0799` (v0.4.4).
- Accepted v0.4.5 economics source: `39d350fa6a3bbfb06672bb5c8edfc1a580d79d0f`.
- Release Prep: `d992e26` on `experiment/v045-release-prep`; version, current
  examples and release notes only. Final artifact qualification remains pending.
- Actual qualified runtime source: `34eaea1df86b57765a4d8b0840845a33d539065f`,
  macOS/Ubuntu qualification run `37994377940`. These results describe that
  source, not either newer report/preparation commit.
- [Accepted economics and impact map](v045-verification-economics.md),
  [handoff](v046-handoff.md), [measurements](../../benchmarks/v045-measurement.md)
  remain inputs. The accepted strict receipt identity model is unchanged.

## Scenario inventory, before API design

| Scenario | Go today | Python today | Required scenario oracle |
| --- | --- | --- | --- |
| A Fresh | `Start(ctx, Options{})`, SQL, `Close` | `start()`, connection, SQL, context exit | committed SQL works; owned runtime disposed |
| B Prepare once | `Database.Snapshot(ctx, SnapshotOptions{})`, `Fork` | `db.snapshot()`, `fork()` | creation ends source DB; children start with schema/data; mutations isolated |
| C Persist/load | `SnapshotOptions.Destination` persists; public load missing | `snapshot_to(path)`, `load_snapshot(path)` | import rejects bad input; source edit/deletion cannot alter imported baseline |
| D New baseline | modified child `Snapshot`, new `Fork` | modified child `snapshot()`, new `fork()` | new baseline includes child changes; original remains unchanged |
| E Application | normal multi-client connections and transactions | normal application connections and transactions | real commit/rollback; connection isolation; disposal cleans all changes |
| F Lifetime | owned backing, `Fork`/`Close` locking | owned backing and inherited child-host FDs | Close races, admitted child independence, repeated Close, error cleanup |

Current maintained owners include
[Go ownership integration](../../tests/gointegration/owned_prepared_test.go),
[Go multi-client integration](../../tests/gointegration/multiclient_test.go),
[Go lifecycle integration](../../tests/gointegration/lifecycle_test.go),
[Python ownership integration](../../tests/test_owned_snapshot.py),
[Python ownership unit checks](../../tests/test_owned_snapshot_unit.py), and
[import/copy tests](../../tests/test_snapshot_copy.py).
Existing coverage is evidence, not proof that the new Go entry has executed.

## Smallest proposed Go acquisition API

```go
func LoadSnapshot(ctx context.Context, path string, opts Options) (*Snapshot, error)
```

`Options` determines subsequent Fork startup/query/shutdown behavior using the
existing defaults. Loading does not start MariaDB. No new file format, save
operation, manager process or cache policy is introduced.

Use [existing import](../../internal/snapshot/owned.go): it captures the external
manifest, copies regular files into private temporary storage, pins read-only
FDs, verifies the owned bytes against the captured inventory/hashes and guest,
and retains that exact verified resource. Fork maps those FDs using the existing
path. Import is not merely a successful verification flag on an external path.

Construct a normal Snapshot with the returned backing and normalized options.
Its Close releases its owned resources without deleting the external artifact.
Use the current Fork/Close lock; children that successfully start can continue
after parent Close. Reject closed baselines with existing errors. Error paths
must return no usable handle and release partial resources.

The existing importer has no context parameter. Check cancellation before
acquisition and after import, cleaning up on cancellation. Do not promise
interruptible copying/hashing without implementing it. Inspect existing error
and platform/legacy-option checks before selecting the final wrapper structure.
Unexpected storage/lifetime redesign returns to Human Review.

After release, focused tests must cover malformed/corrupt/incomplete/foreign
guest inputs, source mutation/deletion, retained identity, cancellation and
cleanup. Real Go integration must prove persisted prepare/load/Fork and new
baseline scenarios; Python supplies equivalent scenario oracles. Run necessary
native macOS arm64 and Ubuntu x86_64 checks for this actual API boundary, not
full unrelated acceptance solely because docs change. Existing runtime receipts
are reusable only when their exact input identity is valid.

## Documentation inventory and proposed boundaries

README currently gives Python runnable lifecycle examples while Go primarily
has install/link guidance. Go persistence documentation explains the missing Go
entry by discussing Python. That asymmetry should be removed after the API
exists; do not write examples against an unimplemented method.

- README: language-neutral product purpose; short Python and Go quick starts;
  Fresh versus reusable baseline; optional persistence; real limitations; links.
- Go guide: Go acquisition, SQL, Snapshot lifecycle, persistence/load, errors and
  cleanup. No Python API tutorial or pytest material.
- Python guide: Python entry points, context managers and pytest fixture use.
  Common contract links rather than repeated architecture explanations.
- Architecture: current ownership and implementation; decisions: constraints;
  historical reports: measurements and earlier hypotheses.

Both language examples must make clear that snapshot success ends the source DB,
each Fork is mutable and isolated, baseline Close releases resources, and saved
artifacts remain the user's regeneration/deletion responsibility. SQL fixtures
are SQL sent through normal connections, not Snapshot files.

Inventory all public fenced examples and validate their actual imports, API
calls, SQL, errors and cleanup. Compile/run Go examples and execute Python
examples using maintained scenario harnesses where possible. Record each
example's owner and result. Installation examples require the corresponding
published version; do not claim future public distribution availability.

## Product Validation foundation and fairness

Reuse the lifecycle/workload foundation in
[v0.4.5 measurements](../../benchmarks/v045-measurement.md) and the maintained
consumer tests. Inspect existing comparison adapters before choosing extensions;
do not create an independent benchmark framework. First prove harness correctness
and equivalent SQL/data oracles, then run one measurement at a time on a host.

| Approach | Isolation and reset responsibility |
| --- | --- |
| Fresh | independent DB, repeated setup, dispose per test |
| Snapshot/Fork | shared immutable baseline, independent mutable DB, dispose per test |
| Testcontainers fresh | independent container/server, Docker dependency, setup/dispose per test |
| Shared rollback | only covered transactions roll back; application commits from other connections can escape |
| Shared reset | explicit data/schema/session cleanup; measure it and verify the next test's baseline |

Use bounded light CRUD, migration/business fixtures, multi-connection commit and
rollback, parallel per-test DBs, and larger prepared data. Include representative
Go and Python scenarios, not syntax parity or a language-speed contest. Record
OS/CPU, exact source/build/guest/container versions, Docker VM/resource settings,
fixture hashes, trials, workers, and phase boundaries. Measure setup, Snapshot,
startup, SQL, cleanup, suite total, CPU and resource footprint. Keep parallel
scalability measurements separate from simultaneous benchmark campaigns.

The earlier native/container pilot used different MariaDB versions and is not a
comparable performance result. Pin comparable versions where practical; if
guarantees or workloads cannot be fairly aligned, return that concrete issue to
Human Review rather than treating all approaches as equivalent. Separate results
where isolation deliberately differs. Container acquisition/image pull conditions
must be reported separately from warm suite runs.

Reuse v0.4.5 Fresh/Fork results only for matching environment and measurement
boundaries: light 32-test suite 2.511/2.635 s, 10 MiB four-test suite 2.540/1.397 s,
100 MiB four-test suite 23.971/7.821 s; Snapshot medians approximately
384/396/661 ms. These are existing observations, not v0.4.6 measurements or a
universal size threshold. No Snapshot optimization is authorized.

## Ordered implementation gates

1. Finish v0.4.5 publication; rebase this plan onto released main and inspect
   actual differences. No automatic main integration.
2. Finalize minimal Load wrapper, implement it and focused import/lifetime tests.
3. Execute A–F semantic scenarios in Go/Python; record exact native evidence.
4. Align README/guides, execute public examples, inspect links and scope.
5. Extend existing measurement harness only as needed; validate its oracles.
6. Run bounded serial Product Validation with explicit isolation differences.
7. Document suitability, limitations, evidence and v0.5 handoff; stop for review.

No new APIs beyond Go loading, guest migration, cache management, shared mutable
fixtures, CI trust-model redesign, Fast Feedback redesign or Snapshot optimization.
This planning branch is not a release candidate.
