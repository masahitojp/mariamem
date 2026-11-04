# Issue53 — Human review G1/G2/G3 follow-up

Current status: G1 implemented and locally verified on clean source_commit
`6d40d0d420bd06cc68e313348a6246787ab51539`; G2 wording is corrected. Canonical
daily (Go tests/vet,67 early source tests,1883 Python tests plus106 subtests and
91 skips), Go/Python source smoke and nine same-source actual-host cases PASS
on macOS arm64 / Go1.26.10 / Python3.14. The host's VCS revision matches and
vcs.modified=false. The subsequent review G3 adds a portable, injected Linux
memory-source boundary and a stdlib sysinfo adapter; its package race tests pass
locally and its Linux/amd64 test binary cross-compiles. Linux-native syscall
execution and the new full platform matrix remain pending. Commit/current local
results below retain their own source scope. Batch full CI after the Human's
remaining review findings; no new heavy run is submitted for this checkpoint.
Existing c53771cd receipts remain unchanged.

Combined G1/G2/G3 runtime source_commit
`e8472b76c90582cef60b5b402faf0cd6ff31905b` subsequently passes the same canonical
daily check (Go tests/vet,67 early source tests,1883 Python tests plus106 subtests,
91 skips) and Go/Python source smoke on macOS arm64/Python3.14. The portable
forklimit package race suite and clean-source Linux/amd64 test compilation PASS.
The nine-case exact-host result above remains explicitly on6d40d0d4; the later
Linux-native assertion and installed/both-host matrix still await CI.

## G1 — cap and occupied-slot diagnostics

The design's diagnostics paragraph required this even though the old eighteen-row
exit did not name a diagnostic assertion. The previous review missed that prose
requirement. The correction puts its checks inside the existing Admission row;
it adds no resource campaign, periodic logger or nineteenth acceptance theme.

The internal pool samples the immutable resolved cap and lease-map size under
one mutex. Reserved, starting, live and unconfirmed-cleanup leases are counted.
Observing diagnostics does not reserve/release a slot or reopen admission.

Go Snapshot/Fork errors, shared-control wait errors and both Go/shared-host Live
capacity errors include, for example:

```text
max_forks=1, occupied_slots=1; close owned children or increase max_forks
```

This is readable error detail rather than a new public options/status API.
Go context error identity remains reachable through errors.Is; public code,
stage and consumed/closed classification are preserved. The capacity remedy is
not recommended for cleanup debt, because increasing a cap cannot reopen that
admission latch.

Private nonblocking fork_reserve full replies also include integer max_forks and
occupied_slots fields. The Python capacity-wait error displays its immutable cap
and last responsive full-reply observation, with the same remedy and existing
pool_timeout/fork_wait/closed=False. If a positive deadline expires before any
capacity reply, occupied_slots is explicitly unknown, never invented as zero.
A missing field from an older development host also remains unknown. All counts
are observations; a concurrent cleanup can change occupancy before an error is
read. They are not a second admission mechanism or a diagnosis of leaked children.

Detection now includes:

- Pool usage across reserved/active/unconfirmed-cleanup/settled owners; diagnostic
  reads cannot reopen admission. ErrFull, deadline and cancellation identity and
  the distinction between capacity tuning and cleanup debt are checked.
- Public Go TestSnapshotCapacityProgressAndWaitDeadline requires both counts and
  the remedy in the HostError, alongside the existing code/stage/errors.Is checks.
- Control TestCapacityReplyAndWaitErrorReportCapAndOccupiedSlots checks integer
  full-reply fields and the direct control wait failure.
- Python test_cap_timeout_retains_child_and_next_close_releases_slot checks the
  public message and existing child survival. Deterministic clock cases require
  last-observed counts or explicit unknown before any reply.
- Existing actual remote-cap and Go consumer / installed Python consumer owners
  now assert the capacity diagnostics as well as their previous behavior. These
  new actual/public source assertions pass locally, including the changed Go and
  source Python consumer. Installed/both-host assertions still need the new
  matrix; old successful artifacts are not relabelled to include them.

Focused local results on macOS arm64 / Go1.26.10 / Python3.14:
Go -race pool/control/public Snapshot targeted owners PASS;61 Python unit,
framed-transport, handoff and Live tests PASS. No guest, generated source, WASI implementation,
SQL wire behavior, version or release-ledger change is part of this follow-up.

## G2 — historical index and current results

The detector map now opens with current source boundaries and links to the later
adoption review / c53771cd assessment, followed by an explicit Historical detector
index —8566c8ad heading. Its no-matrix-PASS / future-execution statements are past
tense and confined to that old checkpoint. Recorded local1870-test evidence and
old source pins are preserved.

The original adoption review is explicitly labelled as the c53771cd review and
links here for the later correction. Project status and usage/release notes state
that c53771cd passed its own matrix, while this G1 runtime delta still requires
new-source verification. The old docs-only tree-equality reuse applied to7c0f6c32;
it cannot cover this later code change. Prose freshness required review; ordinary
CI did not detect the contradictory tense. Documentation/public-boundary and
reference checks apply to this correction.

## Review G3 — Linux physical-memory observation and fallbacks

This G3 is the Human review finding about Linux memory parsing, distinct from
the original design's G3 Python watchdog label.

`memory_linux.go` now calls the Go standard library's `syscall.Sysinfo` adapter,
returning totalram and mem_unit. The conversion must multiply those units, not
assume bytes: [sysinfo(2)](https://man7.org/linux/man-pages/man2/sysinfo.2.html).
The exact MemTotal/kB field is independently parsed from proc; it is total usable
RAM, not free memory ([kernel proc documentation](https://docs.kernel.org/filesystems/proc.html)).
Both reads and cgroup discovery are behind the portable `linuxMemoryLimits`
function with injected syscall/readFile providers. There is no new dependency.

Selection and failure policy:

1. Retain valid finite sysinfo totalram*mem_unit and valid MemTotal*1024
   observations. The existing minimum-selection rule uses the smaller value
   when both work; adding sysinfo cannot override a tighter readable proc view.
2. Either failure is independent: unreadable/invalid proc does not discard valid
   syscall data, and denied/failed/invalid syscall data does not discard proc.
   Zero units/total, parse failure, duplicate MemTotal and multiplication overflow
   mean unavailable, never zero memory, unlimited capacity or wrapped bytes.
3. Cgroup ancestor limits are still read even if both physical sources fail.
   GOMEMLIMIT is still added by Resolve; the minimum valid memory budget wins.
4. Only when every memory observation is unavailable does the pre-approved
   finite GOMAXPROCS fallback apply, with minimum1 and the existing MaxInt32 clamp.
   Keeping that policy avoids an unreviewed sizing-policy change. A fixed fallback
   of1 would be more conservative but is not adopted implicitly here; callers can
   already select an explicit cap. CPU fallback does not establish a memory/OOM
   guarantee and no current-free-memory sizing is introduced.

`memory_sources_test.go` runs on both supported hosts and checks actual expected
byte values/caps: non-byte units, overflow and zero, valid/malformed/missing/
duplicate MemTotal, each single-source failure, differing totals, tighter cgroup/
Go limits, all-sources-unavailable CPU fallback and its minimum. The production
Linux adapter uses that tested boundary, not a second untested parser.
`TestLinuxKernelTotalRAMIsAnObservedLimit` also checks the real Linux adapter's
fields against syscall totalram/mem_unit and inclusion in observed limits. If the
syscall is blocked on a host, that native observation is explicitly skipped;
injected failure-path tests still run. Local macOS package race tests PASS and
Linux/amd64 compilation PASS; native Linux execution is not claimed yet.

## Completion boundary

The Human is still reviewing. This follow-up addresses G1 diagnostics, G2 wording
and G3 memory-source testability; it does not claim the new full installed/platform matrix,
Human adoption, main integration, a new version or publication. Collect further
findings, then run the stable candidate's exact matrix once. The local results
above cover the committed runtime source; an accompanying docs-only result record
must preserve that non-doc tree, and is not a new installed/platform receipt. Any failure remains an unfinished condition, not an accepted exception.
