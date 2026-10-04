# v0.4.2 mmap semantic gate — integration blocked

The released base is **v0.4.1 / 547fb1a6c01e5edb0daa27de273a2e94e66eb098**.
This is an experiment on `experiment/v042-mmap-contract`, with a separate exact-tag
`experiment/v042-release-control` worktree. Main has not been changed or merged;
no release or v0.5 work was started. Read `docs/project-status.md` before preparing
the workspaces. This report is a **negative semantic gate**, not completion of the
requested both-platform/performance acceptance campaign.

## Design and source boundary

The previous opt-in `experiment_mmap` spike was transplanted onto the exact tag:
reserve one anonymous private 2 GiB mapping with PROT_NONE; enable the initial
256 MiB with mprotect; enable newly grown WASM pages under the shared MemMu before
publishing MemSize; retain the same base and full slice header; join workers and
export Snapshot data before munmap. The mapping owner retains the exact original
syscall.Mmap slice. Close is serialized/idempotent and successful munmap clears
ownership. Mapping counters describe virtual/protection ranges, not physical RAM.
There is no CoW, file-backed guest memory, custom pager, guest function/address
patch, Snapshot optimization, forced GC policy or signal-handler workaround.

Experiment changes in production-path files are limited to
`internal/generatedgo/runtime_instance.go` (constructor and teardown) and
`internal/generatedgo/code/base/base.go` (grow callback). New spike files are
`internal/generatedgo/experiment_mmap{,_test}.go`; the new boundary diagnostic is
`internal/generatedgo/v042_boundary_test.go`. The generated constructor and all
p0–p8 function packages are byte-identical to the release. This branch's runtime
spike requires `-tags=experiment_mmap`; it is not a production integration.
Source identities and binary checksums are in [evidence](v042/evidence/).

## Lane A: MMAP SEMANTICS BLOCKED

The small backing adapter is **insufficient to establish the required WASM
contract**. Legal accesses pass, but actual generated scalar accesses violate it.

| Contract | Observed result |
| --- | --- |
| Initial/max size | 4096/32768 WASM pages, 256 MiB/2 GiB; full reserved slice; initial protected tail |
| Stable base / direct generated accesses | Same pointer through grow; real Fn66/Fn68/Fn80 legal loads/stores pass |
| Grow preservation / zero-fill | 1-, 2-, 3-page growth and growth to maximum pass; sampled new bytes zero and old data preserved |
| Failed/over-max grow | Injected ENOMEM and over-max/unsigned -1 growth return -1 without changing logical size or old data |
| Shared worker / TLS / atomic / futex | Child grow visible to parent; shared atomic word, private TLS/stack globals, host wait/wake pass; focused base -race passes |
| Initial OOB / access-width OOB | Actual Fn68 load outside initial logical size, or straddling its end, fatally exits the subprocess with SIGBUS; the embedding process cannot recover an instance error |
| Static offset overflow | Actual Fn80 returns success rather than trapping when an unsigned address plus load offset exceeds 32 bits; the generated uint32 addition wraps into accessible memory |
| Atomic bounds/alignment | Checked helpers reject initial OOB, width crossing, offset overflow and misalignment |
| Direct mapping teardown | Release twice succeeds with one successful unmap; active counters return to zero; mprotect of the former mapping fails |
| Complete failure-path ownership | Normal product failure paths pass; explicit constructor-panic/initial-mprotect-failure/munmap-failure injection and noncooperative-worker containment remain unvalidated |

The failing required-scalar test exits **1**, intentionally retained as failure,
not converted into semantic success by the campaign runner. The runner completing
means the diagnostic captured the expected rejection. See
[required bounds failure](v042/evidence/v042-contract-run02/required-scalar-bounds.log)
and [legal tests](v042/evidence/v042-contract-run02/legal-mapping-contract.log).

The pinned released WASM SHA256 is
`33d351b4edaddce9dd52db375c6c3f2a5ff13c259bc6788794daf5bf8bf3e008`.
Its Fn80 contains **i64.load align=3 offset=8**, encoded `29 03 08`.
Released Go instead emits `*(*int64)(unsafe.Add(mBase, uint32(v8)+8))`.
With stack global G0=8, v8 is -8; the legal clock import receives the wrapping
WASM i32-add output address 0. The subsequent load's effective address is
4294967288 + 8 = 4294967296 and must trap, but the Go uint32 expression becomes 0.
The diagnostic uses a legal deterministic import stub and the **unchanged actual
generated Fn80**. This is not a function-specific patched implementation.
Fn68's separate i32.add +4 legitimately wraps and is **not** cited as this bug.
See [pinned WASM trace](v042/evidence/v042-contract-run02/guest-boundary-trace.json).

A tiny actual shared-memory WASM module, executed by Node's WASM engine, traps
on all three cases and passes initial/max/grow/zero-fill/failure checks. It is a
semantic reference, not a Wasmer fallback-support gate. The
[WebAssembly specification](https://webassembly.github.io/spec/core/syntax/instructions.html#memory-instructions)
requires a non-wrapping effective address and a trap if any accessed byte exceeds
current memory size. Fatal termination of the consumer process is not a safe
replacement for that instance-level trap. The exact-tag released control also executes all three accesses without trapping:
[released control failure](v042/evidence/v042-release-control/released-required-scalar-bounds.log).
Only an opt-in diagnostic test was added on that branch; its runtime is unchanged.
The scalar overflow and logical-bounds defects are inherited from released
generated source; mmap did not introduce their arithmetic or missing checks. Removing
PROT_NONE would merely restore unchecked tail access and fail the same contract.

## Lane B: INCONCLUSIVE

Real macOS arm64 execution on Go 1.26.8 passed the four existing `tests/godefault`
product tests: SQL fixture/use, valid/invalid auth, concurrent fresh instances,
Snapshot/Fork isolation, ordinary failure/corrupt-Snapshot paths, repeated Close
and retained closed handles. Failure-path FD/goroutine counters were 6→6 / 2→2;
retained six closed DB handles kept FDs at 6. The focused runtime/shared-worker/
TLS/futex tests passed, including checkptr=2 for the handwritten adapter tests.
These legal-input checks do not override the failed memory gate.

Ubuntu 24.04 x86_64 execution, installed wheel/SQLAlchemy and GORM acceptance
were **not run** in this campaign after the semantic rejection. No Linux support
is claimed from the old cross-compile evidence or the local aarch64 Docker VM.
A future accepted candidate still needs real Ubuntu execution, both-platform ORM
checks, and complete injected failure-path ownership tests.

## Lane C: INCONCLUSIVE — stopped before performance

No v0.4.1-vs-candidate 1×20/50/100, 4-DB generation campaign or repeated
Snapshot→Fork→use→Close performance scenario was started. A full contract pass
was required before the prior performance experiment; this stronger audit fails
that prerequisite. Old macOS mmap performance evidence remains promising but is
**not** new released-v0.4.1 acceptance or proof of complete semantics.
Ready/CPU/Close/heap/RSS/physical-footprint generation comparisons and Snapshot
amortization therefore remain unanswered. There was no optimization during
measurement and no large soak.

## Disk/resource guards and evidence

The repository experiment-workspace skill/tooling from the retained tooling
branch was used externally; it was not mixed into the released-runtime baseline.
Workspace receipt `base_sha` records that **tooling checkout**, d492e52, not the
tested source base; tested source identities explicitly record released 547fb1a.
All workspaces passed a **16 GiB free-space floor / 4 GiB per-workspace allocated
output budget** before starting, with continuous disk checks and owned child-group
cleanup. Test jobs additionally had 4 GiB aggregate descendant RSS / 6 GiB macOS
physical-footprint limits, 80/85-second per-process CPU limits, FD limit 256, no
core dumps, and phase/outer watchdogs. Sampling was every 0.2 s; short-lived
children can fall between samples, so sampled peaks are not hard instantaneous
OS memory caps. No background guest or large soak was launched.

Candidate run peak owned scratch: **506,269,696 bytes** (~0.47 GiB); baseline
control including checkout: **734,244,864 bytes** (~0.68 GiB). Minimum free space
remained **64,949,620,736 bytes** (~60.49 GiB). Sampled process-tree RSS peaks were
2,911,813,632 / 2,699,919,360 bytes (candidate/control); physical-footprint peaks
were 3,347,795,376 / 3,508,702,760 bytes. These include compilation, and are not
runtime-generation performance measurements. No disk/resource budget was hit.
An initial sandbox ps denial is preserved as setup failure, not a discarded
benchmark sample; the owned temporary directory was cleaned by the runner before
a separately guarded retry. Shared toolchain/Go caches and all pre-existing work
were preserved. Compact logs, receipts, source/binary identity and SHA256SUMS are
retained; disposable completed output is eligible for safe Git worktree cleanup.

## Fan-in / human decision

| Area | Result | Risk | Remaining work | Recommendation |
| --- | --- | --- | --- | --- |
| WASM contract | MMAP SEMANTICS BLOCKED | Fatal scalar OOB; inherited static-offset wrap can access the wrong memory | Decide generic scalar bounds/trap and effective-address contract, then validate all accesses | Do not integrate the current adapter |
| Ownership | Normal release/idempotence and worker join pass | Constructor/OS-call failure coverage incomplete; noncooperative execution still prevents safe unmap | Inject constructor/protect/unmap/startup failures; audit all exits | No all-path teardown guarantee yet |
| Platforms/integration | INCONCLUSIVE | macOS legal-input success is not Ubuntu support | Real Ubuntu24 amd64 and both-platform SQLAlchemy/GORM/wheel acceptance | Defer portability verdict |
| Disposable lifecycle | INCONCLUSIVE | Earlier speedup can hide an invalid memory contract | New guarded released-base and candidate fresh/Fork lifecycle measurements after semantics pass | Keep old performance evidence separate |

1. **Does mmap preserve required semantics?** Not this candidate: scalar OOB and
   offset overflow fail despite legal grow/worker behavior passing.
2. **Is ownership correct on all paths?** Normal joins/idempotent direct release
   pass; complete failure-path proof is still missing.
3. **Both supported platforms?** Not established; only macOS legal-input checks.
4. **Approximately stable repeated create/use/Close?** Not measured in this campaign.
5. **Materially better repeated Snapshot/Fork disposal?** Not measured here.
6. **Bounded enough for v0.4.2 integration?** Not as submitted. The owner/grow
   adapter is small, but generic generated scalar bounds/offset handling must be
   resolved before recommending a production integration plan.

Stop at the human decision barrier. The smallest next decision is whether to
scope a separate **generic memory-access correctness** spike (no function/address
patches, no race census or guest upgrade) before returning to mmap acceptance.
Do not silently widen this spike into generator/runtime redesign, merge or release.
