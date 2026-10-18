# Current main / v0.5.2 product measurement — macOS only

Human requested a repeat of product-oriented measurements and selected macOS only.
No runtime change, Qualification, release or comparison with pgmem/Testcontainers.

Candidate is exact source_commit `2a02e80399dc32eea71c304064b17b8921a0061d`;
baseline is the typed v0.5.2 pin. Both clean source clones build unmodified
ownedprepared and mariamem-host using Go1.26.8, CGO0, Python3.14.8 and the
previous fixed Python dependency list. Observers must match byte-for-byte.
Actual machine is macOS27.0.1 arm64; this is not minimum-OS qualification.

The runner adapts `benchmarks/ubuntu-product/run.py` only for the two fixed
inputs, native macOS identity and resulting inventory counts. Existing SQL,
transaction, child isolation, lifecycle and mapping cleanup oracles remain.

- 8 one-test pilots excluded from performance summaries.
- 84 measured matrix executions: Go/Python, Fresh/Fork, Light, 10MiB serial,
  10MiB four-parallel; 100MiB Fork only; four tests per suite; three trials/input.
- 54 prepared-reuse executions: Python sharedhost small/medium with two children,
  100MiB with sixteen; six ordinary pairs and three separate RSS-observed pairs.
- Total146 executions, sequential campaigns with alternating/rotating input order.
  Keep all slow trials. No new profiling or 100MiB Fresh investigation.

Report preparation/Snapshot/child-ready/SQL/Close and full user workflow,
CPU, cumulative Go allocation and RSS separately. Go's existing heap observer
remains enabled; its product wall excludes diagnostic probes, not all observer
overhead. Python matrix post-SQL samples are not peak memory. Resource-observed
reuse must not be pooled with ordinary latency. Pairs share one machine/window;
do not compare historical absolute timings as if environment were unchanged.

Budget: 7200s including builds, 900s/cell, 1800s/reuse campaign, nested scratch
10GiB, outer owned workspace12GiB, free reserve12GiB. The existing observed
6GiB Go RSS ceiling is not a hard RAM quota. Missing cells, identity/oracle
failure, unreclaimed mapping/scratch or budget breach means incomplete.

Use the experiment-workspace runner with an owned venv and pinned Go bin on PATH.
The measurement workspace must be new and inside disposable temp. Preserve
compact outputs/identities and this recipe, then remove cloned source, binaries,
venv and build/module caches. Main adoption and publication are separate decisions.
