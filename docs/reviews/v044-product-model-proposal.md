# Disposable database and reusable initial state

Status: proposal under exploration, October 7, 2026. Product Contract Audit
Decisions 1–6 have not been adopted. Earlier support/preferences were incorrectly
recorded as adoption; this document now preserves discussion material only.
No product/API/integration decision follows from this proposal.

## Core uses and concepts

mariamem gives a test a real, mutable MariaDB and discards that database when the
test ends. The application may use its own connections and commit normally.
Light setup can be repeated in each new database. Expensive migrations and
fixtures can be prepared once and reused as an immutable initial state.
Each database created from that state starts independently; one test's writes
must not become another test's initial state. Isolation of external services,
application processes and connection pools remains the caller's responsibility.

The two required concepts are a mutable disposable Database and an immutable,
lifetime-bound Snapshot. External prepared-state import is an advanced boundary;
failure diagnostics are a separate concern. Neither requires a persistent save
point as part of the ordinary prepare-once/test-many workflow.

SQL/transaction and ORM consumers and installed-wheel pytest-xdist acceptance
support these uses. Heavy migrations, real HTTP applications and imported dumps
remain useful workload candidates rather than verified framework promises.
Reusable setup is optional; no universal Fresh-versus-Fork crossover is promised.

## Snapshot and Fork names

Keep Snapshot and Fork. The behavior is to fix database state and generate
independent databases from it, which fits the names. Template/Spawn would describe
the testing role more directly, but would still need source-lifecycle and cleanup
explanations. Names alone cannot establish isolation or ownership.

- Successful snapshot creation ends its source Database. Resolve transactions,
  commit setup and close clients before taking it. Precondition rejection keeps
  the source usable; failure after acceptance can consume it.
- A Snapshot provides a fixed initial state to multiple Forks. Its lifetime is
  explicitly owned by the caller or fixture.
- Fork starts an independent mutable Database with the captured schema/data.
  Closing that child discards its mutations and leaves the Snapshot reusable.
- Closing the Snapshot prevents further Forks. Children that successfully started
  remain independent of the Snapshot handle's later Close.

Fixture descriptions must state both the shared object and its duration.
A session baseline and a session/class mutable database are different contracts.
Current `mariamem_snapshot` shares initial state per xdist worker/session;
`mariamem_fork` creates and closes a database for each test. Current class-fork
fixtures actually share one mutable database across methods; their removal has
not yet been approved. Setup builders are not ordinary mutable test databases.

## Documentation responsibilities

README and language guides own current usage, lifecycle, guarantees and limits.
Architecture owns how the current implementation realizes them. A proposed decisions directory
would own adopted reasons and invariants that constrain future work. Benchmark and
investigation reports own historical evidence with source/date/measurement bounds.
Project-status owns current release state, limitations and selected next direction.

Do not make users reconcile historical CoW/Wasmer/allocator statements to use the
current API. Preserve historical evidence and license/provenance obligations;
label and route it rather than rewriting old measurements as current results.

## Product and public API decisions still pending

All six audit decisions remain under exploration. Decision 4 includes several separate choices: path writes, external import,
constructor aliases, backing introspection, mutable class fixtures and setup
fixtures. Support for the concepts or OwnedPrepared is not recorded as product adoption
or authorization of API removal. Path-based reads/import remain acceptable; arbitrary
path-based Snapshot writes are the maintainer's removal direction, with the
specific API migration still to be settled.

The maintainer reports no intentional dependency on the imported path-write,
reopen or class/session mutable-sharing APIs. Pre-1.0 compatibility is not a
reason by itself to retain them. Conversely, mere duplication is not proof that
an alias must be removed to enforce ownership.

## Evidence

- [Product Contract Audit](https://github.com/masahitojp/mariamem/blob/25a537c9fdb112c89d3e17c69ca078ffc4ad1f82/docs/reviews/v044-product-contract-audit.md).
- [Owned Snapshot integrity proposal](v044-owned-integrity-proposal.md).
- Current behavior remains documented in [Go](../go.md) and [Python](../python.md).
