# mariamem v0.5.3 — Reuse successful macOS platform checks

This release reduces repeated platform-check work when starting or forking
databases on macOS. A successful check is reused within the same Go process,
including the managed Python host shared by a Snapshot lineage. This avoids
repeated macOS version-probe subprocesses on subsequent starts.

## Startup behavior

Concurrent callers share an in-progress check. Failures, unsupported-platform
results and cancelled checks are not cached as success. Waiting callers retain
their own cancellation, and a failed or panicking probe releases its waiters.
Ubuntu platform checking is unchanged.

Public Go/Python APIs, in-memory Snapshot ownership and parent/child isolation
are unchanged from v0.5.2. This release does not change database initialization,
SQL execution, the guest, or Snapshot storage.

## Validation and distribution

The platform-check change passed focused native macOS/Ubuntu development CI,
and its main integration passed the canonical development check and integration
suite. See the [implementation and adoption record](../docs/reviews/macos-platform-cache-results.md).
These earlier checks are not relabelled as final-version artifact qualification;
Release CI must accept the exact v0.5.3 source and its artifacts before publication.

Bounded macOS product measurements against v0.5.2 observed shorter small Fork
workflows, with smaller or mixed differences elsewhere. They do not establish
uniform performance or memory improvements. The
[measurement report](https://github.com/masahitojp/mariamem/blob/94f13e6/docs/reviews/current-product-macos.md)
retains all measured conditions, including higher sampled RSS in the separate
large Python resource-observed cohort and its unresolved cause.

MariaDB remains 12.3.3. Guest/converter inputs, supported platforms and minimum
Go version are unchanged: macOS 15+ arm64 and Ubuntu 24.04 x86_64, Go 1.26.0+.
Assets remain host-only Python wheels, common corresponding source, provenance
and SHA256SUMS. This release does not publish to PyPI.
