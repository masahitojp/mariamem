# mariamem v0.4.3

Architecture consolidation and characterization of the generated-Go runtime.

- Retire live Wasmer execution, native bundle resolution/cache/provisioning,
  legacy executable packaging and related release gates. Generated-Go is the
  only supported runtime; legacy overrides now fail explicitly. Historical
  reports/reference tools and required corresponding-source notices remain.
- Document Snapshot as cold prepared files and Fork as fresh MariaDB execution.
  Prepared file-backed MAP_PRIVATE views use OS page-level CoW; no running
  runtime clone, custom CoW filesystem or Unix fork is implemented.
- Separate Fork integrity-validation cost from mapping/server initialization
  and recurring large COUNT scans. Fresh versus Snapshot/Fork guidance remains
  workload-dependent; no memory or latency guarantee is added.
- Preserve v0.4.2 controlled pure-memory32 traps and mmap lifecycle behavior.

Supported acceptance scope remains macOS 15+ arm64 and Ubuntu 24.04 x86_64.
Full generated-guest race cleanliness and non-cooperative forced termination
remain known limitations. No Snapshot API/ownership change, hash-verification
optimization, guest upgrade or unrelated performance optimization is included.
