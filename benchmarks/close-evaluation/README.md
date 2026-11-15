# Finite Close evaluation (#206)

Plan: same connected product source f563128520fc49097ac83ef47cdea2dee21ff62a,
Go1.26.10/macOS arm64, GOMAXPROCS8/GOGC100. Build identities and the committed
harness source_commit are recorded before running. No product runtime edits.

Each fresh process creates 1,000 (id,v=id) rows, snapshots once, then processes
48 private children with P workers. Each child verifies COUNT/SUM, updates id0,
verifies its value, closes its SQL pool and waits for disconnect. Compare public
Close with internal stopForCleanup. Every handle is finally Waited and Disposed
checked, all leases must return and mapping count must match pre-batch baseline.
The primary timer includes all 48 children, final drain and Snapshot.Close.
Process wall/CPU/peak RSS include setup and process exit. Batch CPU is sampled
at the two batch endpoints; no per-stage instrumentation runs in the plain build.

Cells P/cap = 1/2, 2/4, 1/1, 2/2. Separate one-process warmup per arm/cell,
then five alternating pairs per cell = 40 measured processes. Round order rotates
cells; even rounds sync→stop, odd rounds stop→sync. Fixed 150ms inter-process
pause. Diagnostic runs follow all measurements: one per arm/cell, separately.
Smoke and two race workload processes precede warmup. All runs, failures and
outliers are retained. No extra sampling or removal of slow pairs is authorized.

The diagnostic overlay changes only evalDiagnostic=false to true, adding
backend close/stopped/cleanup-end events and mapping samples. It calls the same
admission Acquire then forkReserved path to mark real startup admission after
waiting, whereas the plain arm uses public Fork. Its cleanup window includes
remaining runtime/transport/transfer work, not only munmap. Event recording can
perturb scheduling; do not use its times as the performance estimate. Mapping
counts are point samples (a lower bound on the maximum); the runtime's existing
peak logical RW bytes counter is also retained, not equated to physical RSS.

Both arms include #203–#205. This isolates waiting policy within the candidate,
not its total overhead relative to old main. No public async API or adoption is
established. Improvement must include final drain; unconfirmed disposal fails
the run. If no consistent whole-batch benefit appears, recommend withholding
adoption rather than expanding into an indefinite search. 70-test suite and
platform qualification require a separate continuation decision.

Budget: one local host, two hours active work, at most 90 minutes per guarded
execution, 16GiB owned scratch and 12GiB free-space reserve, no heavy CI.
If a safety failure or budget breach occurs, stop, preserve evidence and report
what remains rather than dropping requested cells or checks.

Run the committed campaign with a prepared experiment workspace path argument.
The experiment-workspace runner supplies TMPDIR/GOTMPDIR and storage guarding.
