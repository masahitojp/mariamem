# mariamem v0.6.1 — Prepared Django tests and finite Fork capacity

## Prepared Django tests

- New opt-in `mariamem.django.prepared_database`, `PreparedDiscoverRunner`,
  `PreparedTestCase` / `PreparedTransactionTestCase` and
  `mariamem.django.pytest_plugin` prepare migrated/seeded state and give each
  test an independent Fork of its prepared class state. Committed writes, DDL
  and ordinary assertion failures do not become the next test's initial state.
  Install the optional `django` or `django-pytest` extra and explicitly select
  this entry. The ordinary standard-runner recipe remains available.
- `prepared_database()` is declarative. Settings import, check/shell, discovery,
  collection-only and database-free suites do not acquire a host. SQL outside
  the owned test lifecycle is refused before connecting. Preparation/retirement
  failures retain their errors; unconfirmed cleanup stops dependent admission.
- Local pytest-xdist workers are supported with explicit `-n N` and `load` or
  `loadscope`. Each DB-using worker owns its own host and migration/seed baseline;
  controller, idle and DB-free workers acquire none. A replacement worker
  prepares a fresh lineage. Hard worker death cannot run Python temporary-file
  finalizers, so job scratch cleanup remains necessary.
- The extras accept Django 5.2 LTS, 6.0 and 6.1 (`Django>=5.2.8,<6.2`).
  Django 6 requires Python 3.12+; Python 3.11 continues with Django 5.2.
  Maintained Release profiles are Python 3.11 / Django 5.2 and
  Python 3.14 / latest Django 6.1.

This entry supports one default database alias and explicit prepared classes.
There is no class-wide atomic: class preparation is committed and `on_commit()`
may run immediately there; per-test TestCase atomics remain. Do not combine
prepared Django with routing/`shadow_maria` ownership in one invocation, or mix
ordinary database test classes/function-style `django_db` tests into the prepared
run. Unused routing bindings now report `UnusedRoutingWarning` after successful
cleanup. Remote workers, automatic worker counts, other xdist schedulers and
Django `--parallel` remain outside the accepted scope.
See the [prepared Django guide](../docs/django-prepared.md) for setup and worker sizing.

## Finite Snapshot/Fork capacity

**Behavior change:** omitted Snapshot Fork limits now resolve to a finite,
memory-based capacity. Full capacity waits before another child starts;
reserved, starting and cleanup-pending children retain their slots until actual
retirement. Capacity is per Snapshot, not a process-wide or machine-wide limit.

- Go adds `SnapshotOptions.MaxForks` and read-only `Snapshot.MaxForks()`.
  Fork waits honor the caller's context. Closing the parent wakes waiters
  without closing successful children. Use keyed `SnapshotOptions` and
  `HTTPConfig` literals: adding fields breaks old positional literals.
- Python adds `snapshot(max_forks=...)`, read-only `max_forks`,
  `fork(timeout=...)` and `Database(snapshot=..., fork_timeout=...)`.
  Cross-host children keep their origin slot through disposal. Supplied pytest
  fixtures add `mariamem_max_forks` (default `None`, automatic) and
  `mariamem_fork_timeout` (default 30 seconds). Acquisition failure stops
  dependent admission in that worker; ordinary assertions retain their behavior.
- Go Live requires at least two slots and reserves replacement capacity before
  draining. A full parent returns busy while preserving the current generation.
  Go test helpers retain their default of two; `HTTPConfig` exposes an override.
  Python E2E `Config.max_forks` reaches its Live baseline and rejects one before
  preparation. Prepared Django forwards `max_forks` / `fork_timeout` to its
  run/class baselines and child acquisitions, including final DROP cleanup.
- Capacity diagnostics include the resolved limit and observed occupancy
  (or explicitly unknown), with guidance to close children or increase the cap.

Nested acquisition while holding every slot can wait indefinitely. Release a
child first or bound the wait with a Go context / Python timeout. Automatic
sizing is a memory heuristic, not an OOM guarantee or a CPU/latency optimum.
Hidden/unreadable cgroup limits can cause host-RAM sizing to over-admit; configure
explicit caps and choose the total worker count separately. Independent root
`Start` / `start()` calls are outside these caps.

Failed capture cleanup has an accepted permanent failure path: if a newly owned
Snapshot also fails Close, the shared host latches `captureDebt`, retains its
origin slot and stops parent admission even after runtime disposal. Cleanup
retry or Live Reset cannot clear it; safely close remaining owners and prepare
a fresh lineage. This differs from retryable child cleanup debt.
See [Go](../docs/go.md), [Python](../docs/python.md) and the
[adoption decision](../docs/decisions/issue53-fork-limit-adoption.md).
PR #85 is merged; older candidate records describing integration as pending
retain their historical context.

## Fixes

- Local test endpoints accept arbitrary handshake usernames and password
  responses, allowing applications to retain placeholder test credentials.
  Protocol validation remains; all sessions use the existing embedded guest
  privilege context. This adds no authentication, account management or
  credential isolation. See [connection behavior](../docs/python.md).
- `import_dump` now rejects statements above the existing 1 MiB text SQL budget
  during preflight, before connecting, instead of advertising a 4 MiB reader
  limit that execution could not accept. The limit counts transmitted UTF-8
  bytes, including leading whitespace/comments. Source-location diagnostics
  and failed-source discard remain; file/count limits stay 16 MiB / 10,000.
  See the [dump format contract](../docs/importing-dump.md).
- The WASM buffer-pool allocator avoids redundant allocation/zeroing work by
  passing its existing extent alignment to the internal allocator. Zero-filled
  memory and allocation/free semantics remain. A small retained-RSS saving was
  observed; CPU/batch speedup is inconclusive and queue latency is unmeasured.
  See the [bounded allocation decision](../docs/decisions/buffer-pool-alignment.md).
- Host WASI writes propagate zero-byte write errors, including broken pipes,
  and preserve actual short-write progress. This fixes the tested interrupted
  guest cleanup stall; the accepted prepared CALL observations remain unchanged.

## Compatibility and validation

MariaDB remains 12.3.3. Python minimum remains 3.11 and Go minimum remains 1.26.0.
Supported hosts remain macOS 15+ arm64 and Ubuntu 24.04 x86_64. Distribution
continues through GitHub Release assets; no PyPI publication is added.
The [v0.6.0 wire/connector limitations](../docs/../release/NOTES-v0.6.0.md)
continue to apply. No general SQL compatibility or throughput/peak-memory
improvement is claimed.

Installed prepared-Django and local-xdist acceptance passed on both supported
OSes with Python 3.11/3.14 under their
[Django](../docs/reviews/d1-release-41327745652/README.md) and
[xdist](../docs/reviews/d1-xdist-adoption.md) receipts. The finite-Fork matrix passed
on exact candidate `cddd8dcbd6d664171907ffc1769b83e472640875`; see the
[source-bound receipt](../docs/reviews/issue53-fork-limit-evidence/ci-41778273108/README.md).
These results are not relabelled as acceptance of the final 0.6.1 source. CI ownership/cache consolidation after 0.6.0 is maintenance, not added
product compatibility evidence.

Before publication, finalize the selected 0.6.1 source and notes, then submit
that exact candidate to Release CI for qualification and the authorized
operation. Release CI owns acceptance, publication and public smoke.

