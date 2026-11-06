# Issue68: sampled undo-page latch owner

**Result: IO ownership observed for six short waits; long UPDATE NOT_REPRODUCED.**
This answers the narrow holder-kind question for the new samples. It does not
identify the holder or cause of the earlier355ms UPDATE.

## Recommendation

Prioritize the page-write/completion path over transaction-to-transaction
contention if the investigation continues: all six captured page-wait
registrations have FOR_IO ownership and WRITE_FIX state. Do not yet change a
parameter or host shim. Missing evidence is which stage (pre-submit work,
queued IO, IO execution, or queued completion) consumes time during a long
wait. This experiment observes none of those queue-stage timestamps.

A further natural repeat is not part of this task. Distinguishing those stages
would require another bounded collector and a matching event; its reproduction
cost remains uncertain. Artificial delay would validate a mechanism, not prove
the old event's root cause.

## Source and protocol

- Product: `1862f4a89397bddfa1820d835106d3437a438cf7`.
- Measured harness: `f678de708c7e376f53b6d021976fc7f17827e3e4`.
- Guest input: `6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe`.
- Binary SHA256: `55222550661e15d87a2deb2a446eecda1e2b9e7409a845525506ea2131c260fc`.
- Local macOS arm64, Go1.27.3, GOMAXPROCS8, Pipe, explicit cap equal to P.
- Both buffer-pool load/dump OFF, commit1, O_DIRECT, read1/write2,
  purge1,16MiB buffer pool; effective SQL assertions on root and eight children.
- Three natural processes: P8/P4/P8,48children each. No extra natural repeat.
- Three controls: effective settings, artificial SQL sleep/profile binding,
  wrong seed (expected failure). All completed with cleanup and no leftover
  owned DB temp. SQL/isolation/affected-row/value oracles passed in natural runs.
- Build/collector/selector tests and focused observer race tests passed. Initial build attempt could not download
  a fixed Go dependency inside the sandbox; the approved network retry succeeded.
  No DB process was started by that failed build. No CI or product adoption.

The diagnostic overlay instruments generated host code; canonical guest input
and product source are unchanged. This is not an uninstrumented performance run.

## Observations

| Natural batch | Parallel | Children | Max UPDATE ms | UPDATE >100ms |
|---|---:|---:|---:|---:|
|0|8|48|6.041417|0|
|1|4|48|6.353542|0|
|2|8|48|9.613875|0|

All six page waits matched their rollback-segment scope's actual buffer page:
space1/page3, writer mutex block+24. At registration, owner-before and
after were4294967295 (FOR_IO), mutex word held, state0xc0000001 (WRITE_FIX plus
one buffer fix). Owner scope entry also observed IO in each case.

- Registered-to-return waits:0.083500–3.239375ms; median0.486313ms.
- No natural100ms owner sample, no >100ms page wait.
- One short wait resumed about1.145ms after the after-close timestamp;
  do not describe all six durations as entirely before notification.
- Scope-end owner reads were UNRESOLVED, consistent with sampling immediately
  after the internal writer mutex is acquired and before page owner is installed.
  They are not evidence that the original owner remained until scope end.

These page IDs belong to the new six samples. The old355ms profile did not
record its page ID; do not retrospectively assign1/3 to that event.

## Collector boundaries and controls

The exact generated p3 hash and offsets are pinned in ../layout.json. Only
Fn18164 L272's call to Fn16621 is wrapped, with the actual fixed buffer-page
pointer. Existing query/rseg/AtomicWait/notify pairing is retained. Sampled
fields are owner156, mutex24, readers148, state172 and immutable page ID0/4.
The non-atomic recursive field152 is deliberately not read.

Samples are taken at scope entry, actual wait registration, and at most once
100ms after registration if that wait has not returned. Scope-end is diagnostic.
A threshold callback is not itself proof the thread is still asleep: its sample
must be compared with the matched signal-before/after timestamps. No acquisition
history is recorded and stable owner reads do not exclude intervening changes.
I/O ownership does not prove a physical disk write or queue blockage.

Unit controls cover IO/thread/zero/changing owner, absent mutex ownership,
page mismatch, namespace isolation, late callback, wait return/scope end and
post-flush cancellation. The synthetic late test uses a shortened timer; it is
not a natural long-wait observation. The artificial SQL-sleep control validates
the inherited query/profile gate, not IO latch ownership.

## Reproduction and retained evidence

`python3 analyze.py --check` reads raw-evidence.tar.gz without extraction,
recomputes summary.json and compares it without modifying evidence. SHA256SUMS
binds the compact report, raw archive, CSV, analyzer and source/build identities.
The archive retains all six process outputs, traces (including empty traces),
controls and unit/build logs; raw SHA256 manifest binds each member.

To rerun, prepare a disposable workspace and check out the measured harness
commit into its worktree. Copy ../build.py and ../run.py into its evidence/
directory, then run them with the recorded Go version and budgets. Source
identity and clean-tree checks precede compilation, and overlay hashes are
recorded in inputs.json. Do not run them inside the report directory. No new
build is needed to replay this report.
