# Scoped history wait candidate — UNQUALIFIED

The native candidate is feasible and passes the bounded correctness checks.
Normal P8 timing does **not** establish either an ordinary speedup or resolution
of the intermittent 400ms wait. Recommend advancing the narrow native fix to
canonical integration verification after the Human's adoption decision, based
on the previously observed missing notification and the explicit wait contract.
The strongest objection is that this normal campaign had no long-wait recurrence
in either arm; it cannot demonstrate notification-to-WRITE recovery or guarantee
that this candidate removes every tail. Do not add another unguided campaign or
make scheduling-gate success a prerequisite.

| Normal full P8, 20 processes per arm | main | native candidate |
| --- | ---: | ---: |
| Whole-process median, ms | 512.547 | 522.200 |
| Whole-process maximum, ms | 617.841 | 601.645 |
| Suite median, ms | 505.126 | 515.155 |
| CPU median, ms | 2630 | 2660 |
| Peak RSS median, KiB | 643874 | 643666 |
| Samples at least 400ms / 420 | 0 | 0 |
| Maximum sample, ms | 194.868 | 131.907 |

The geometric mean of ten balanced block ratios is candidate **+0.836%**;
candidate is faster in 4/10 blocks, range −11.016% to +9.982%.
All 40 full suites passed (2800 case bodies), as did two semantic prechecks.
Every first full-suite observation is retained. These are shared-host results,
without resetting OS caches; batch-first does not mean independent cold host.
Rebuilding also relocates reviewed globals by 64 bytes and data by 16 bytes, so
small timing differences cannot be uniquely attributed to waiting notification.

## Candidate and verification boundary

`guest/experimental.patch` modifies four upstream C++ files. It uses the public
read-lock try API and notifies only the contested `history_size` slow path.
Native pool TLS/state and mutex protect ownership: skip nonworkers, inactive,
long and already-waiting workers; roll back begin failure; finish only the
owned scope. The original wait APIs, 400ms timer, SQL, and Snapshot/Fork behavior
are unchanged. The native contract test uses actual candidate bodies/header and
a scheduler seam; it is not a full engine build.

The actual guest compiled successfully in [CI 46128641933](https://github.com/masahitojp/mariamem/actions/runs/46128641933).
Fresh translation/installation and real SQL commit/rollback, Snapshot, three
Forks and Close passed. Actual CRC tests passed 832 length/alignment cases plus
the independent known vector, and 80 valid/corrupt/LSN page cases. Worker
reclamation, failure and wait tests passed, together with 128 Python input,
installer and binding checks. The complete product/generated inventories were
checked again after testing and benchmarking.

The original single-guest installer correctly rejected the new identity.
The experimental development route now has an exact profile: full reviewed
worker bodies, unchanged TLS bytes and CRC table, relocated globals, and the
renumbered CRC function. Canonical guards remain unchanged. A failed/partial
installation was not benchmarked. The final rerun includes the relocated CRC
differential test fixture. This profile and workflow are experiment support,
not material to merge wholesale into main.

## Exact inputs and reproduction

* Baseline source commit: `e00b3ec41f9c5d4ca3f85db4ff73198dbf3613e9`.
* Native guest source commit: `d9f8bc50bcd14ac5ea0dc1a01f7d29bdc1248398`.
* Verified host-stage source commit: `d29c1d3b1091e8f2893bdfbdd41b808cf5a7876b`.
* MariaDB source commit: `e4549ea60c98a8743ed4743d7f92174d8a0005d9`.
* Harness source commit: `1977fff480c2f976bc23f4d2e1b8ff8db36ad128`.
* Candidate guest SHA256: `e6d0570841d79b82cfee1a87070080febeb08da6dba1727c5341e53ae6463c9b`.

Check source object identity with `scripts/git_identity.py` before any build.
Use a clean checkout of the recorded guest source on the pinned arm64 workflow
to rebuild the UNQUALIFIED single guest, or retrieve its CI artifact. Use the
recorded host-stage source for `regenerate_release_guest.py --development`,
with a fresh output outside that checkout. The guest origin and host-only
changes are independently verified. Do not relabel either artifact with the
later recipe commit. Install pytest9.1.1 and PyMySQL1.2.3 in an owned venv.

Extract these recipe scripts into an owned workspace with `worktree/` at the
recorded host-stage commit and `temp/dev/` containing the verified development
output. Set `WAIT_NOTIFY_WORKSPACE` to its absolute path. Run `prepare.py control`
and `prepare.py candidate`, then `compare.py` after all build/guard processes
have exited. Preparation archives the baseline and immutable original harness,
then uses Go1.27.4, CGO0 and GOMAXPROCS8. Only module replacement/tidy changes the
harness; original Go/SQL bytes and dependency sums are verified.

The fixed comparison is ten alternating CKKC/KCCK groups, each process P8,
GOGC100, MaxForks16, matched70 cases, audit UPDATE OF and revenue preaggregation
enabled, synchronous Close, in-process API. Two semantic prechecks are separate.
The original harness trace is used; no added diagnostics, gates or timer changes.
The committed `plan.json` predates execution. `result.json` retains all block
results; detailed runs, traces, input hashes and reduced verification records
are in the parent workspace's `evidence/`.

No main integration or release was performed. Canonical patch promotion,
accepted bindings/provenance regeneration and normal platform acceptance remain
outside this task. Future upstream updates must recheck the native wait API and
the existing allocator/CRC bindings; update effort beyond this candidate has
not been measured.
