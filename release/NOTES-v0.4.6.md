# mariamem v0.4.6 — Product Usability & Validation

- Go adds `LoadSnapshot(ctx, path, opts)` to load a saved baseline without
  starting a database. Loading validates and owns the state; subsequent Forks
  are independent of source-path changes and sibling mutations. The saved
  Snapshot format is unchanged.
- README and language guides give Go and Python comparable examples for Fresh,
  prepare-once/Fork-many, optional persistence and cleanup. Expensive setup may
  be shared as a fixed baseline; each test normally owns its mutable database.
- Bounded workload and data-type validation documents when Fresh is sufficient,
  when preparation reuse helps, and how database-instance isolation differs
  from a shared server with reset. Measurements are workload-specific guidance,
  not general speed or complete MySQL compatibility guarantees.

Supported platforms remain macOS 15+ arm64 and Ubuntu 24.04 x86_64. Minimum
versions remain Go 1.26.0 and Python 3.9; release validation uses Go 1.26.8 and
Python 3.14. MariaDB and dependency versions are unchanged.

Saved baselines remain optional derived artifacts: users manage their freshness
and deletion. Loading checks cancellation before and after import, rather than
interrupting its copy/validation work. Live baselines retain backing-file FDs.
Forced cleanup of hung execution and general race-detector cleanliness remain
outside the guarantees. No Snapshot or filesystem optimization is included.
