# Host-mounted versus guest-memory restore source

## Condition and source facts

This is a disposable probe on `experiment/prepared-auth-keys`, not a production
restore optimization. Results are pending the dedicated CI run; no new p50/p95
or architectural conclusion is claimed yet.

Both conditions use existing test RSA keys, active caching_sha2_password with
loaded-key/public-key checks, the same within-call validation-reuse probe, the
same Wasmer/MariaDB configuration and the same 64 KiB stdio snapshot_copy routine.
A single canonical Go benchmark process creates one 1,000-row Snapshot, then
Forks that **same immutable Snapshot** for both conditions at workers 1/4/8.
The launcher alternates host-first / guest-first across 20 measured pairs and two
warmup pairs. All clients/processes close before switching the process environment.

- **Control:** `/snapshot-in/data` → fresh memory-FS `/mariadb`.
- **Probe:** the unchanged routine first copies `/snapshot-in/data` into fresh
  memory-FS `/restore-source`, then copies `/restore-source` → fresh `/mariadb`.

The pre-stage is measured separately with identical operation counters. It is not
free or removed from Fork latency. The source copy remains alive until process
exit, adding ~138 MiB of logical file contents to the probe; memory pressure and
warm caches are therefore experimental confounders, especially at workers 8.
This is not a claim that production can retain such state cheaply.

## Correctness and observability

Before the probe's timed copy, recursive comparison checks original versus
pre-staged source: exact directory inventory, regular-file sizes and full byte
contents (stronger than comparing computed hashes). After either condition's
copy, the same comparison checks original versus destination. Extra/missing files,
symlinks, altered bytes and copy failures reject startup. No redo/undo files are
omitted. Each timed copy independently reconciles inventory sizes against both
read and write bytes in the reporter; pre-stage relative-path inventories must
also match the measured guest-source inventory.

These comparisons run **outside copy timing** and their wall/process/thread CPU
are recorded as `restore_verification`. They do add to end-to-end startup, and
probe performs one additional comparison. They can warm the source before the
probe's timed copy. Neither comparison nor pre-stage is silently subtracted.
The pre-existing `restore_begin`→`restore_complete` events cover the whole
restore operation, including these costs; `restore_copy.wall_ns` isolates the
actual comparison copy. Do not confuse these scopes.

`restore_source`, `restore_identity_verified`, `restore_copy`, and (probe only)
`restore_prestage` are structured guest startup JSON. Clock failures remain
fail-closed. `summary.json.source_boundary` retains operation wall/CPU, bytes,
calls, per-file data, pre-stage and verification distributions with raw observations.
The ordinary lifecycle waterfall still reports full Fork→SQL and restore envelope.
The benchmark validates first SQL plus 27 loaded-key checks per paired execution
(one Start and 13 Forks per condition). No expensive memory diagnostics run.

## Execution and pending analysis

Dispatch the existing guest-boundary workflow with `source_boundary=true`.
It builds the changed guest identity once, then platform AOT once on macOS arm64
and Ubuntu 24.04 x86_64; exact verified artifacts can be reused afterward.
Results live under `init-source-boundary` inside the usual initialization artifacts.
Raw results remain ignored. No production provenance is updated.

Analyze copy-only p50/p95, read/write wall and CPU, total CPU, pre-stage costs,
verification costs and full Fork→SQL at workers 1/4/8 on each platform separately.
Use per-pair differences; never add marginal medians. Compare read growth with
write/materialization growth and document the extra memory/warmth asymmetry.
Host-mounted reads include WASIX servicing, runtime transfer and host filesystem
access; no physical disk attribution is possible from these counters alone.

## Recommended restore direction

Pending measured evidence. This probe is intended to discriminate source-boundary
work from common materialization work. Recommend exactly one next direction after
both platform results arrive; choosing it now would assume the experiment's result.
No source/destination optimization or larger VFS/CoW work is implemented here.

## FAST tranche integration checkpoint

**Prepared RSA keys:** existing causal evidence is sufficient to move to a separate
productionization task after this probe. Still require provisioning/lifetime/security
policy, missing/corrupt-key diagnostics, actual authentication-handshake coverage
(current startup retains grant bypass), and packaged Go/Python lifecycle, Snapshot/
Fork, multi-client and interrupted-query cleanup on both supported platforms.

**Within-call validation reuse:** existing paired evidence supports a separate
productionization task. Still require explicit verified-identity ownership,
mandatory native/snapshot integrity checks, mutable NativeDir/sidecar and failure
paths, and packaged lifecycle/cleanup on both platforms. No persistent trust cache.
Neither experiment is merge-ready merely because its measured savings are clear;
neither is integrated by this task.
