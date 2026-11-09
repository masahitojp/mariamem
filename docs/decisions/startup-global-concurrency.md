# Keep normal global concurrency during InnoDB startup

On2026-11-09 the Human chose to advance the bounded startup-concurrency remedy
into a production adoption candidate. This authorizes the minimal canonical
patch and its verification. It is not a claim that the candidate has passed,
landed on main, or been released. The8MiB buffer-pool candidate remains separate.

## Decision and boundary

Keep the existing normal global thread-pool concurrency during buffer-pool
startup loading and redo application. Change exactly two calls from
`set_concurrency(srv_n_read_io_threads)` to `set_concurrency()` in
`storage/innobase/buf/buf0dump.cc` and `storage/innobase/srv/srv0start.cc`.
Update the recovery comment that otherwise falsely describes a temporary cap.
The following reset calls remain; no work or synchronization is removed.

Normal selection uses the existing hardware-concurrency calculation and min/max
clamps.16 was observed on the experiment host; it is not hard-coded, an exact
worker count, or a new public option. Read group1, buffer pool16MiB, load/dump
settings, recovery, task ordering, waiting accounting, host shim, API, Snapshot
ownership and cleanup semantics are unchanged. No observation hooks are adopted.

Recommendation: advance this focused mitigation. The decisive evidence is the
same-request global admission rejection plus the intervention with the read task
group held fixed. The strongest objection is that the largest gain occurred
under intrusive diagnostics; observation-disabled long PREPARE calls remain and
CPU increased slightly. The chosen scope accepts a mitigation candidate, not a
complete latency fix or a proven stable variance reduction.

## Evidence, with original identities

Starting product/base_commit: `a3b2b6457147e2b8edbd31fec77ab6ec04f11b22`.
MariaDB source_commit: `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e` (12.3.3).

- [Startup intervention report](https://github.com/masahitojp/mariamem/blob/87510b1a909d14846d010a62f6e575d7887f951b/benchmarks/issue140startupcap/results/README.md):
  measured source_commit `8d36aed9054618f0ed6993bfdedaab69d0119acc`.
  Mac/Go Pipe/P8/cap9/shop70; five alternating pairs per observation mode.
  Observation-disabled whole-suite medians738.690/663.754ms, MAD188.434/94.319ms,
  CPU2806.114/2853.875ms, process peakRSS756.406/766.266MiB. Wall wins3/5;
  PREPARE>=100ms remains4/315 on each arm. A mixed RSS pair increases148MiB.
  Disabled hooks still incur short-circuit overhead. These are descriptive
  small-cohort results, not a stable speedup/variance or resource bound.
- Diagnostic global>=100ms requests2072/17675 to0/17976 in that cohort are
  correlated requests, not independent stalls. Do not advertise the diagnostic
  wall reduction as a production52% speedup.25 valid processes/1750 SQL cases
  and cleanup passed. Invalid first-attempt records remain excluded.
- [Later16/8MiB comparison](https://github.com/masahitojp/mariamem/blob/260633b8c36078d5830983217ec2ed53a2c61920/benchmarks/issue88cappool/results/README.md):
  measured source_commit `73c358ebdb06ed88f8da1d45af8abaa2d0655425`.
  With this remedy active, one8MiB diagnostic process still had a389.421ms
  initial global queue wait and244 correlated long requests. No initial-stage
  blocked-gate event was retained. A later completion-stage rejection does not
  explain the earlier wait. Do not claim all tails fixed or attribute that
  isolated result to8MiB. This is a different cohort, not a new control arm for
  the startup-only comparison.

These are generated-Go overlay experiments on one Mac. They are not canonical
C/WASM build acceptance, Ubuntu evidence, fresh-root gains or proof of a common
cause with the older #68 UPDATE/UNDO reports. #140 stays open for residual waits.

## Fixed adoption exit and detection

| Condition | Current state / detection |
| --- | --- |
| Minimal canonical patch; no observer/8MiB/read4 changes | Source candidate prepared; inspect diff against the base above |
| Both actual prepared C regions retain load/recovery, mutex and reset order | `startup_concurrency.validate` runs during source preparation; unit mutations reject restricted/hard-coded cap, omitted work/reset and changed lock; real pinned-file patch application checked locally |
| Canonical guest and translated Go are generated and bound to the candidate | PASS at d3cc4807 /42531554501: two equal independent C builds, both110-file generated inventories equal the candidate, full build guards and20 negative mutations per host. Original bootstrap stays UNQUALIFIED |
| macOS15 arm64 and Ubuntu24.04 x86_64 correctness | PASS on canonical guest8e3761ea at d3cc4807 /42531554501: actual worker/CRC/UCA/lexer controls, J1, normal/binary-prepared native SQL, two independent children, cleanup and Snapshot smoke on both hosts |
| Resource/performance claims remain bounded to original receipts | Accepted reporting limit; normal CI does not prove variance reduction or a CPU/RSS upper bound. No requirement for all400ms tails to vanish |
| Minimal protected integration and accurate current records | PENDING. Preserve original receipt identities; exact candidate/source and required strict-base PR checks, then main-adoption review. Do not merge exploratory history |

No further parameter sweep, larger-working-set8MiB test, general worker-accounting
investigation, or performance campaign is added to this adoption exit. A concrete
new failure may require diagnosis; it must be recorded rather than converted
into an open-ended extra acceptance program. Version selection, Qualification
and publication remain separate decisions.

## Staged implementation

Stage1 is an exact-source single C bootstrap build using the existing explicit
UNQUALIFIED route. New bytes are not yet known, so the old canonical guest hash
must not be forged or silently rebound. The dedicated workflow has one100-minute
job and no automatic retry. Its successful artifact is an input to installation,
not adoption PASS. Preserve compact source/checksum receipts; keep WASM/build
payloads in CI artifacts rather than Git.

Stage2 installs regenerated Go/guest identity and updates the existing generated
ownership/provenance records, then obtains independent reproduction and both-host
acceptance. No removed or relaxed correctness gate is permitted. A draft source
candidate is not merge-ready while generated bytes still represent the old guest.

## Current implementation checkpoint

[Bootstrap receipt](../reviews/startup-cap-ci-42509593737/README.md) authenticates
one source build. [Installation](../reviews/startup-cap-installation/README.md)
records guest8e3761ea and bounded local verification on clean source1b446e53.
[Canonical receipt42531554501](../reviews/startup-cap-ci-42531554501/README.md)
closes the independent-build/both-host rows at exact source d3cc4807. No old
performance result is rebound to this artifact. Development42531563986 separately
failed because the candidate workflow had an automatic push trigger. Remove that
trigger, keep manual dispatch and all execution steps, and retain the existing
policy test. The repair passes120 focused tests and5 subtests locally; protected
PR checks and the main-adoption decision remain outstanding. This receipt update
changes no guest/runtime/generated bytes. It does not reopen parameter sweeps or
add another performance campaign to the fixed exit.
