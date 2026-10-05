# v0.4.2 heap-backed memory correctness continuation

Basis: `56be628bf2d976048c5ea6d1949879781ed75342`, on isolated branch
`experiment/v042-controlled-traps`. Released pure memory32 only; unchanged
2 GiB Go-heap backing, initial logical memory 256 MiB. No mmap, benchmark,
soak, main merge, version bump or publication.

## Finding and bounded compatibility layer

The existing effective-address/bounds implementation replays the reviewed WASM
fixtures correctly. Its shared `ThreadLaunch` recovery boundary, however,
re-panicked inside a child goroutine. A root/host recover cannot intercept that
panic; a guest memory trap on that worker could terminate the Go host.

The additional `controlled-thread-traps.patch` changes the pinned converter's
shared thread helper, not generated functions or individual addresses:

- keep the first worker panic under a mutex in the instance's shared ThreadPool;
- join workers and return that failure through `WaitThreads`;
- retain failure across repeated joins, rather than consume it into success;
- relay through `SpikeWait` for existing join callers.

The handwritten `StartInstance` adapter uses `executeGuest` to recover the root,
join workers on normal return **and root failure**, and return controlled errors
before descriptor/prepared-file cleanup. A failed execution does not export a
snapshot. Cleanup errors remain joined to initialization/root errors.

This is **cooperative failure propagation**, not forced instance cancellation.
A blocked root or non-cooperative peer may prevent the join/error return. It
does not prove immediate whole-instance termination on every worker trap.
Keeping resources owned until users exit is deliberate; premature cleanup
would make a later mmap owner unsafe. This existing hard-failure limitation must
remain an explicit input to a separate mmap integration task.

## Verification

All requested checks passed on macOS 27.0.1 arm64 with Go1.26.8. Ubuntu was
not executed in this continuation. The guarded replay and compact result are in
[`v042-controlled-traps.json`](v042-controlled-traps.json).

| Check | Result |
| --- | --- |
| Reviewed deterministic matrix | 2,472 matched; 1,693 expected traps; host exit 0 |
| Extra maximum-boundary checks | 7 expected traps; grow/data/zero/base/state pass |
| Controlled root/worker traps and cooperative join | PASS |
| Focused runtime/thread/TLS/futex/race | PASS |
| SQL/CRUD, auth, sessions, Snapshot/Fork, repeated Close | PASS |
| Independent regeneration / provenance / retained license examples | PASS / PASS / 34 examples |
| Canonical Go tests/vet, Python, public-source check | PASS; Python 432 passed / 6 skipped |

The deterministic fixtures cover scalar widths, SIMD, atomic/RMW and alignment,
boundary crossing, non-wrapping static offsets, valid accesses, observable
trapping loads, old data and zero-fill, stable base, multiple/zero/max/failed
grow, and partial memory effects before a later trap. Reviewed reference results
were not rewritten. Reduced max-grow fixtures use three pages; the actual
generated guest test separately checks its 256 MiB initial boundary and valid
growth with shared worker visibility/TLS globals.

Additional runtime tests cover root/worker scalar/SIMD/atomic traps as returned
errors, same-host fresh-instance survival, retained first failure/concurrent
joins, root+worker error preservation, partial initialization, and no completion
before cooperative worker exit. The real generated scalar access is also
executed on a worker and relayed through two successive joins.

Focused product acceptance checks SQL/CRUD, two simultaneous sessions, auth
rejection followed by a usable session, Snapshot/two independent Forks, and
three Start/Close cycles. Focused runtime/host/thread/futex race tests run;
full generated-guest race adaptation is not claimed.

Canonical verification includes the unchanged local check, byte-for-byte
independent regeneration (including handwritten integration tests), guest/data
identity and provenance, and positive retained native license-symbol evidence.
Normal generated functions are byte-identical to the basis; generated-code
changes are confined to `base/base.go` and `base/spike_wait.go`.

## Boundaries and next decision

The source pipeline applies the extra shared-helper patch and carries the
handwritten regression tests in independently regenerated trees. Original
source/notices, guest/toolchain inputs and the existing memory lowering stay
unchanged. The guarantee remains the released pure memory32 recipe, not
memory64, assembly/fused backends or extra translator modes.

The passing candidate can be used as the heap-only base for a separate mmap
reconsideration task. That future task must still validate mapping lifetime, grow,
platform behavior and failure-path ownership; a passing bounds matrix is not
proof of forced worker termination. No performance or cross-platform readiness
conclusion is made here. Stop before integration at the human decision barrier.
