# Actual prepared-lexer C candidate measurement

The bounded actual-guest acceptance passed on both OSes in CI42437059943.
This campaign measures the actual C candidate against adopted product bytes,
using the same Go1.27.3 direct Pipe harness/SQL/seed on one Mac. Historical
Go-overlay timings are not substituted for C measurements.

`plan.json` fixes52 processes: four correctness/negative controls, twelve warmup
processes, and36 primary processes (three alternating pairs per Fresh/Fork P1/P4
off, plus Fork P1/P4 on). Each primary/warmup has48 independent children and1000
seed rows. Keep all samples and tails; report per-child p50/p95 and >100ms counts,
whole-batch wall/CPU and process RSS. Process RSS is not per-child retained RSS.
Stop at this finite campaign or a failed correctness/input/budget guard.

`build.py` creates an exact detached6134274a source worktree and reuses the fixed
C artifact. It checks adopted runtime continuity to3d8b2201 and verifies all108
installed C runtime source files against the accepted CI receipt. Only source
provenance differs by path. The measured harness source has its own exact Git
identity. Both measured arms use Go1.27.3; the regenerated dev smoke host retains
its CI-pinned Go1.26.10 and is not the measured binary.

Ordinary binaries have no Go experiment overlay. Diagnostic binaries use only
the existing generic `forkstages/overlay.py`, identically on both products. The
traces separate memory construction, API/runtime startup, server_init and routine
preparation; they do not identify common/InnoDB/plugin components inside
server_init or the owner of a SQL/UNDO wait. Observer cost is reported against
the ordinary binary; do not sum medians or assign traced intervals to off totals.
The recipe does not authorize adoption, another optimization or release.

Run in an owned experiment workspace with10GiB budget and12GiB minimum free:
commit the harness, create the disposable Python venv with pytest9.1.1 and
PyMySQL1.2.3, then run `build.py` and `run.py` with that Python. Both use owned
Go caches and guard disk/process limits. Keep compact observations, source/input
hashes and final report; remove the nested detached worktree using Git before
normal experiment-workspace finalization and cleanup.
