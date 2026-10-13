# v0.5.0 startup tail: InnoDB setting spike (macOS arm64)

**Result: `innodb_flush_sync=OFF` did not cover the approximately one-second
startup tail.** In 30 alternating ON/OFF blocks of the existing four-parallel
Fresh fixture, OFF had a tail in 29/30 suites versus ON in 19/30; 11 blocks
had a tail only with OFF and one only with ON. The setting was read back through
SQL before measurement. Both arms completed every existing SQL, transaction,
and cleanup oracle. This bounded experiment supports *not* adopting this
setting as a startup-tail mitigation; it neither tests every InnoDB setting nor
qualifies a product change.

The [wakeup spike](v050-startup-tail-wakeup-spike.md) directly observed the
current guest's missed notification: the cleaner read a zero target, the main
thread set a target and signaled an empty condition list, and the cleaner then
registered for a roughly one-second timed wait. In the [pinned MariaDB source](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/buf/buf0flu.cc#L2570-L2611),
the initial target read and choice to wait precede the later processing that
branches on `srv_flush_sync`. MariaDB documents `innodb_flush_sync` as a
checkpoint I/O-burst policy, ON by default, rather than a control for condition
notification ([system variable](https://mariadb.com/docs/server/server-usage/storage-engines/innodb/innodb-system-variables#innodb_flush_sync),
[page flushing](https://mariadb.com/docs/server/server-usage/storage-engines/innodb/innodb-page-flushing)).
Changing I/O capacity or dirty-page thresholds may alter scheduling and the
frequency of this mode, but the source-level read/wait ordering remains.
The observed OFF tails were **not** instrumented to prove they all used the
same exact condition-wait sequence.

## Inputs and method

- The v0.5.0 annotated tag object is
  `bfd854da1cecbe71ad761d1578b3f2c710a1c07f`; it peels to source commit
  `44100ec676c8c9064f32f3a01bd9a990d487bb61`, checked with
  `scripts/git_identity.py inspect v0.5.0`. Canonical guest Wasm SHA-256:
  `7c7b6ce5168a1a0d98019751b4c36c25f2e9948dbae0124ec3f434efb0b8642c`.
  The exact released Generated Go file used as input has SHA-256
  `8f99ee297e51ccfddfb5920c2618fd73250d5978fdf6e7076ffecc8012a22667`.
- This is a **disposable translated-Go configuration prototype**, not a
  rebuilt guest. [`build_config.py`](spikes/startup-tail-v050/build_config.py)
  copies the exact release source, preserves all 25 existing embedded-server
  arguments, and adds one argument to `mysql_server_init`: either
  `--innodb-flush-sync=1` or `--innodb-flush-sync=0`. The two copies differ only
  in that value. A separate Start/SQL probe returned `1` and `0` respectively.
  The [build record](v050-startup-tail-config-evidence/config-build.json) has
  patched-file, probe and binary hashes. No canonical guest or product source
  was changed.
- Both binaries were built with Go 1.26.8, `CGO_ENABLED=1`, `go build -p 1
  -trimpath -buildvcs=false` on macOS 27.0.0 arm64. Python 3.14.8 ran the
  harness. The existing OwnedPrepared fixture uses 10 MiB of deterministic
  data, eight InnoDB tables, four independent Fresh DBs, four workers,
  application connections, SQL/commit/rollback and cleanup oracles. Each arm
  ran in its own process. [`compare_config.py`](spikes/startup-tail-v050/compare_config.py)
  alternated ON-first and OFF-first order for 30 blocks; no successful trial
  was retried or discarded. The threshold `ready >= 900 ms` is the earlier
  approximately-one-second mode classifier, not a pass/fail limit.
- An initial sandboxed attempt failed before any DB started because local TCP
  listen was denied. Its [failure log](v050-startup-tail-config-evidence/config-failure-00-flush-sync-1.txt)
  is excluded. The full campaign ran outside the sandbox and has
  [inputs](v050-startup-tail-config-evidence/config-comparison-unrestricted-inputs.json),
  [all 60 suite records](v050-startup-tail-config-evidence/config-comparison-unrestricted.jsonl),
  [console record](v050-startup-tail-config-evidence/config-unrestricted-console.log),
  and the deterministic [reduction](v050-startup-tail-config-evidence/config-summary.json).

| Four-parallel arm | Suites with tail | Tail Starts | Suite wall median |
| --- | ---: | ---: | ---: |
| `innodb_flush_sync=ON` | 19/30 | 28/120 | 1.860 s |
| `innodb_flush_sync=OFF` | 29/30 | 46/120 | 1.917 s |

Eighteen blocks had tails in both arms, eleven only in OFF, one only in ON,
and none in neither. The paired OFF-minus-ON wall-time median was +0.178 s.
The prior released-binary spike saw 18/30 ON/default tail suites in its own
campaign, but cross-campaign counts are not pooled or treated as a controlled
comparison. This experiment is macOS-only and uses a prototype translated-code
argument insertion; it cannot establish the exact tail rate of a canonical
guest rebuilt with the setting. It does show that this setting does not
eliminate the tail in the tested v0.5.0 behavior.

## Decision boundary

Keep the v0.5.0 InnoDB defaults. Do not expose `innodb_flush_sync=OFF` as a
tail workaround. Tuning `innodb_io_capacity`, dirty-page thresholds, buffer
pool or redo size would change workload/flush scheduling without removing the
observed target-read/condition-wait ordering, and is not an established fix.
The v0.5.0 embedded guest has fixed startup arguments; a SQL `SET GLOBAL`
after Start cannot affect a delay inside `mysql_server_init`.

The earlier post-lock target-recheck candidate remains the direct fix
hypothesis. Advancing it needs the [wakeup spike's stated boundary](v050-startup-tail-wakeup-spike.md#judgment-and-next-boundary):
source-level state-machine review, canonical guest rebuild and regeneration,
flush/checkpoint/shutdown correctness, and product-platform validation.
This spike performs none of those integration steps and does not change the
Human decision recorded in the [review](../docs/reviews/v050-startup-tail-wakeup-human-review.md).
