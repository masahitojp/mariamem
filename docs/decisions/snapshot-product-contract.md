# Disposable databases and fixed baselines

Status: maintainer-approved v0.4.4 product contract; implementation qualification
and release approval remain separate.

## Product boundary

mariamem provides disposable real MariaDB databases for tests. Each test normally
owns one mutable DB; application connections can commit/rollback normally.
Disposal is the isolation boundary. It is not an automatic test-transaction
wrapper and not a persistent database service.

Expensive migrations/fixtures may be prepared once and shared as a fixed
Snapshot baseline. Fork creates independent mutable DBs from it. Child writes
never change the parent or siblings. A modified child can create a new baseline.

Snapshot/Fork names are retained because they describe fixing a state and
creating independent DBs from it. They do not promise Unix process-fork or
running-runtime cloning semantics.

## Lifecycle and persistence

Successful Snapshot creation ends the source DB. Precondition rejection keeps it
available. Closing the baseline prevents new Forks; successfully started
children own their lifetimes and remain usable until separately closed.

`snapshot()` fixes the current DB state. `snapshot_to(path)` additionally persists
it. Persistence is requested when the baseline is created; an existing baseline has
no later save/persist operation. Explicit persisted outputs are
advanced derived artifacts: code/data inputs remain reproducible and the user
owns freshness, regeneration and deletion policy.

Python `load_snapshot(path)` acquires such a baseline without starting a DB.
Existing constructor/open/start entrances remain available, but ordinary guides
prefer module acquisition and lifecycle operations. Internal path, manifest and
validation methods are not public concepts.

Debugging artifacts and automatic cache management are separate possible
concerns; neither defines Snapshot semantics or enters v0.4.4.

## Integrity follows ownership

Acquisition completely verifies prepared inventory, content and guest identity.
mariamem owns the exact verified backing; supported operations never mutate it.
Fork uses that same resource with cheap structural/lifetime/compatibility checks,
without recomputing full content hashes.

External imports cross a filesystem trust boundary. An independent internal
copy is verified against the input's expected inventory/hashes, then owned.
Changes/deletion of the source after successful acquisition cannot affect Fork.

The contract explicitly does not promise detection on every Fork of silent
media corruption arising after acquisition. It is not an adversarial same-user
security boundary. Reducing repeated verification is supported by exact resource
ownership, not a path name, timestamp or cached boolean.

## pytest boundary

Baseline preparation may be session-scoped; mutable child state is
function-scoped. Built-in class fixtures that carry mutations between tests are
removed. Test classes remain useful organization and may use the function
fixtures. Deliberate custom sharing is not prohibited by the Python language,
but is outside the default isolation contract.

No new run-wide/shared fixture is added. Each xdist worker owns its session
fixtures. Fixture ergonomics are deferred to v0.6.0 dogfood evidence.

## Consequences

The owned implementation holds approximately one read-only descriptor per
prepared file for the Snapshot lifetime. External import includes a private-copy
cost; acquire once and Fork many to amortize it. These costs must be reported
with preparation/cleanup included rather than inferred from hash percentages.

[Current architecture](../v04-generated-go-architecture.md) records HOW.
[User guide](../python.md) records ordinary operations.
The prior OwnedPrepared spike is feasibility evidence, not final production
performance or release qualification.
