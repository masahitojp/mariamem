# v0.5.0 page-cleaner source correction — macOS arm64 spike

**Decision: integrate the narrowly scoped MariaDB source correction through the
canonical guest path; this experiment branch is not itself merge-ready.** The
current guest's observed early-signal ordering has a source-level correction.
Two Linux arm64 development builds produced the same patched Wasm, two native
Wasm→Go generations produced identical executable bytes, and 30 balanced
four-parallel Fresh pairs each in Go and Python saw no `ready >= 900 ms`
candidate Starts. Functional and lifecycle oracles passed. This is bounded
evidence for the identified one-second mode, not a promise that every startup
tail has been removed.

The [prior ordered trace and translated-code hypothesis](https://github.com/masahitojp/mariamem/blob/experiment/startup-tail-wakeup-v050/benchmarks/v050-startup-tail-wakeup-spike.md)
showed the cleaner read `buf_flush_sync_lsn=0`, the main thread set a checkpoint
target and signaled an empty condition list, then the cleaner acquired the
flush-list mutex and registered for a one-second timed wait. The
[InnoDB-setting comparison](https://github.com/masahitojp/mariamem/blob/experiment/startup-tail-innodb-config/benchmarks/v050-startup-tail-config-spike.md) did not mitigate
that mode. This spike applies the same guard to the pinned MariaDB source:
once the mutex is held, the cleaner waits only when the target is still zero.
It leaves the existing idle-vs-timed wait choice unchanged when zero. A target
that arrived while the cleaner acquired the mutex now bypasses that wait and
is processed in the existing loop. The target writer and condition signal are
under that mutex. The patch does not modify the checkpoint operation itself.

## Fixed input and source review

- v0.5.0 tag object `bfd854da1cecbe71ad761d1578b3f2c710a1c07f`
  peels to source commit `44100ec676c8c9064f32f3a01bd9a990d487bb61`
  (`scripts/git_identity.py`); released guest SHA-256
  `7c7b6ce5168a1a0d98019751b4c36c25f2e9948dbae0124ec3f434efb0b8642c`.
- MariaDB 12.3.3 is pinned to upstream commit
  `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`. The exact
  [source file](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/buf/buf0flu.cc)
  has raw SHA-256 `593c16448b8775055e5aa3d48b36a21dd5152bbfbac675c0f9713b0c0183a620`.
  The candidate [experimental patch](../guest/experimental.patch) has SHA-256
  `d59f6ad6c8b0406038a1fdcc36efd07fb624e898dadacd45bbef5cc7515c0cd5`.
  It applies with `patch --batch --forward --fuzz=0 -p1` to the pinned source.
- The patch uses an atomic target load while holding `flush_list_mutex`. The
  source's `buf_flush_wait` sets the target and signals while holding this
  mutex. The check closes the traced interval between the loop's pre-lock read
  and the wait decision. It deliberately does not change other wakeup paths.
  The `srv_flush_sync=0` branch, alternate shutdown phases and sustained
  checkpoint pressure were not independently stress-tested here.

## Rebuilt guest and native generation

On clean experiment commits `484dadbe80c09c6bea17eb12ac30d1cf7e2d37bd`
and `ad83e0039415a9277363d4cbdb32f21107cfbf13`, a fresh Linux arm64
builder (`mariamem-wasix-build:0.4.7`, image ID
`sha256:3ded805d8dcae3ffdf39515c3f0540b27b695719570903594452f8787abe570f`)
ran `scripts/build_generated_guest.py --development-output <fresh path>` from
the repository's pinned source, patches and toolchain. The second commit only
rebound the existing worker-lifetime guest identity guard after validating its
three protected normalized function hashes and module shape; it did not relax
those guards. Both builds produced Wasm SHA-256
`7d1330e67b06eb810d0fafd649df0944dbca1b20cd7e49f8e5ecdde7f5ac8c09`.
These are separate **UNQUALIFIED** builds at different source commits, not the
canonical same-commit two-build release recipe.

The first native generation stopped at the expected old-guest identity guard;
the [failure record](v050-startup-tail-source-fix-evidence/native-first-failure.json)
is retained. After exact hash rebinding, two independent
`scripts/regenerate_release_guest.py --development` runs at `ad83e00` both
passed compilation and SQL/transaction/Snapshot/Fork/Close smoke. The raw
converter translation identity and executable SHA-256
`89278ac72c0c2badc019c13a3e62adb202f971a68ffe571570066cecaa83721c`
match. Of 94 generated-inventory files, 93 have matching hashes; only
`provenance.json` differs because the development `installation-inputs.json`
records the absolute translation output directory. Once that field is removed,
the installation inputs match. Full [identities](v050-startup-tail-source-fix-evidence/identities.json)
and [phase receipts](v050-startup-tail-source-fix-evidence/) are retained.
Neither development receipt substitutes for canonical provenance.

## Balanced product observation

The [comparison program](spikes/startup-tail-source-fix/compare.py) used one
unchanged v0.5.0 release-source binary and one rebuilt source-candidate binary
per arm, with exact binary hashes in the [Go](v050-startup-tail-source-fix-evidence/source-fix-go-inputs.json)
and [Python](v050-startup-tail-source-fix-evidence/source-fix-python-inputs.json)
input records. Thirty blocks alternated arm order. Each arm ran four Fresh
databases concurrently, 10 MiB, eight tables and four workers; the existing
SQL, commit/rollback, connection and version oracles were kept. No completed
trial was retried or discarded. `ready >= 900 ms` is the pre-existing tail
classification. Suite is the frequency unit because four Starts in one suite
are correlated. The [raw records](v050-startup-tail-source-fix-evidence/) and
[reduction](v050-startup-tail-source-fix-evidence/summary.json) preserve all
60 arm runs per language.

| Four-parallel Fresh | Tail suites | Tail Starts | Suite wall median | Paired candidate minus baseline wall median |
| --- | ---: | ---: | ---: | ---: |
| Go v0.5.0 | 24/30 | 31/120 | 1.751 s | — |
| Go source candidate | 0/30 | 0/120 | 0.947 s | -0.787 s |
| Python v0.5.0 | 23/30 | 33/120 | 1.789 s | — |
| Python source candidate | 0/30 | 0/120 | 1.066 s | -0.718 s |

The candidate also passed the existing integration-tagged
`TestDefaultReleaseFailurePaths`, `TestClosedDatabaseRetainedPipeLifetime`, and
`TestLoadSnapshotPersistedLifecycle` on macOS arm64; see the
[test log](v050-startup-tail-source-fix-evidence/source-fix-lifecycle-tests-integration.log).
An initial invocation without `-tags integration` compiled no test files and
was corrected before execution; it is not a product failure. No Ubuntu product
run, long-run pressure test, race conclusion or release qualification was made.

## Integration boundary

This source correction removes an observed unnecessary wait without changing
the requested flush work. The strongest objection is that the page-cleaner
state machine has more conditions than the traced startup path; the bounded
test does not prove every flush/shutdown interleaving, and a different tail may
still occur. The next integration should move only this hunk into
`guest/source.patch`, remove `guest/experimental.patch`, update the worker guard
and guest/generated-source identities, and perform the canonical two-build and
independent native regeneration with source/license/provenance guards. Run
focused checkpoint/shutdown and Start/Close tests plus Go/Python consumer
comparison on supported platforms before merge. Do not promote this branch or
interpret the zero observed candidate tails as a universal latency bound.
