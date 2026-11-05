# Issue #65 — 3D.1 native protocol stopped-root capture/Fork

**PASS for the bounded macOS arm64 experiment.** A real native-protocol client
prepares InnoDB data, consumes its source into a stopped-root Snapshot, and starts
two fresh generated-Go children with independent writes. Rollback, baseline Close,
child recapture and Go Pipe capture work in this isolated route. Recommend the
separate Linux x86_64 repeat before a Live campaign. Do not adopt the fixture yet:
public API/CI integration and full protocol/consumer qualification are unfinished.
The strongest concrete objection is that existing Go owner tests bind production
Fn indices and do not compile against this development guest.

The Human selected implementation of [3D.1](../../../docs/design/issue65-native-protocol/snapshot-fork.md)
after [3C](../issue65-go-wire/README.md). This is not public Snapshot/Fork wiring,
Live, main integration, issue closure, version placement or release approval.

## What actually ran

The [final suite](evidence/suite-final-control.txt) passes **14 top-level cases**,
including 12 control-failure subcases; [results.json](evidence/results.json) names
each. The same final binary also reruns the four 3C protocol/deadline/isolation
cases. The separate [controlled-worker test](evidence/runtime-capture-final.txt)
passes at the actual adapter's execution/capture boundary.

| Observation | Evidence |
| --- | --- |
| Active transaction rejection preserves the source; rollback=true retains committed id1 and excludes uncommitted id2 | CaptureForkRollbackAndRecapture; restored row identity checked, not just row count |
| Two children isolate writes; closing the baseline leaves children usable and rejects new Fork; modified child captures again with ids1/3 | Same case, existing bound-root/COW library and a private finite pool of2 |
| Idle server-prepared session retires; session variable is absent in a fresh child | Same case; no THD/NET/statement/socket/lock serialization |
| Busy SQL, a partial header and64KiB outstanding output reject capture without consuming DB; other SQL/control still progress | CapturePartialAndOutputRejection, then finish/read the pending commands |
| Queued INSERT held before admission cannot execute after fence; duplicate fence/stop creates one receipt and one root transfer; wrong stop ID rejected | CaptureQueuedFenceAndDuplicate; restored InnoDB row oracle |
| Concatenated native commands with a warmed NET buffer work; foreign-epoch capture rejected without damaging source | CaptureConcatenatedInputAndForeignEpoch |
| Actual Go Pipe connection captures and restores | CaptureGoPipe; same admission/transport path, no public Pipe API change |
| Missing mysql.proc restores fail before READY; joined failed startup releases its lease | CaptureRejectsInvalidRestore; its bootstrap FAIL stderr is expected negative evidence |
| Lost/invalid fence, stop ACK or final receipt never publishes a baseline; unsent cancellation preserves DB, cancellation after fence consumes it | CaptureFailureControls |
| Ordinary STOP/private EOF cannot authorize capture; modeled cleanup/shutdown errors deny it | CaptureOrdinaryStopAndEOF and failure controls |
| Actual host awaitJoined retains occupied/blocked capacity until join and capture disposition; permanent capture debt survives later resource cleanup | CaptureJoinCancellationRetainsLease and CaptureDebtCannotBeForgiven |
| A failed translated-runtime worker with a deliberately blocked peer cannot complete join/freeze; releasing the peer permits error completion | Controlled ThreadPool test, with the same executeWireCapture helper used by the real adapter |

Capture events assert: native stop receipt and successful translated worker join
precede approval/freeze; freeze precedes memory release; host reader/relay joins
precede TakeRoot/OwnRoot publication. Native started==joined==rollback_reports is
checked for successful captures. Session result16/17 during expected owner stop
is NET interruption, not by itself a failed capture.

## Mechanism and source boundary

Go owns TCP/Pipe transport, temporary attach gating, capture IDs, disposition and
backing/lease ownership. Guest keeps the shared SQL admission/transaction gate.
TRY_CAPTURE atomically rejects busy/transaction state or irreversibly fences SQL.
CAPTURE_STOP is separately correlated; expected owner-stop is set before closing
Vio waits or client sockets. Late DATA cannot grow fenced queues or enter SQL.
Host validates stop acceptance and final receipt; a one-shot approval channel
lets the runtime freeze only after executeWireGuest has joined every guest worker.
No reader-exit/join cycle is introduced. Ordinary shutdown or failed execution
cannot acquire a root. Duplicate stop is tested as two identical adjacent frames;
there is no promise of a new reply from an already exited runtime.

The native-only cleanup hook observes the **existing** trans_rollback(this) result
inside THD::cleanup, after its original table/temp cleanup. No duplicate rollback
call is retained. Missing rollback reports or a reported failure deny capture.
Restore maps the existing prepared root into mariadb and validates routines/keys
before READY; it does not repair schema or run fixture SQL against restored data.
The former effects-table creation/post-STOP diagnostic SQL are removed from this
entry. Canonical guest/source.patch and production Go/generated runtime remain
unchanged. The C++ transport/timer controller still co-locates fixture duties;
controller relocation is not part of3D.1. Normal MySQL bytes remain opaque in Go.

## Identities and checks

- Guest source_commit:5d9915d9940ff691249361aafb6ea39551f29a87.
- Final guest SHA256:c4c72644cd3fa4605a936a7eafe8d622ab4f670e5b7bdbfbdf30f0a351e8dfcf;
  18,437,746 bytes, one canonical LLVM23 development build, **UNQUALIFIED**.
- Host base source_commit:ecd5d2b7ceff2085cac59f629c36d688007fc6bc.
  Experimental templates are additional inputs, inventoried explicitly.
- [Final compiled source/binary record](evidence/host-build-final-control.json):
  Go1.26.10, CGO_ENABLED=0,7,158 staged source files, final template hashes and
  binary SHA. [Guest receipt](evidence/guest-final.json) pins archives/toolchain,
  prepared source and exact Git source; later report commits are not that source.
- Three worker-lifetime bodies match reviewed ABI after recorded relocation and
  function renames; explicit development binding only. Production pin unchanged.
  Existing Python binding tests21/21 and wrong-guest/full-body-hash controls2/2 pass.
- Artifact/source hashes and three added patch/source blocks checked; Python AST,
  relative links, public-source and diff checks. No broad product/release acceptance.

## Original failures and qualification limits

Initial positive tests raced the final output ACK and received a valid busy
rejection after the driver returned. Positive/fault setup now waits for actual
IDLE; rejection behavior was not relaxed. Initial logs remain. The preliminary
explicit rollback was replaced by observation in upstream cleanup's original
position; its earlier guest and test receipt are not final acceptance.

The full Go generatedgo test package failed to compile because existing memory
owner tests call production-specific Fn66/68/80 etc. No tests were deleted or
weakened. The focused command uses Go's actual GoFiles/build-tag selection plus
the new boundary test. That test passes; the ordinary package suite does **not**
have a pass claim. Port these guest-index test bindings before product adoption.
The first host receipt also sampled external test-template hashes after they had
advanced; its exact compiled source inventory and staged copies are retained with
an explicit note. Final assemblies assert immutable source/template/tool hashes.

Faults are explicit models: INJECT1 forces cleanup-failure disposition, INJECT2
forces shutdown-failure disposition, and a host hook models captured-root cleanup
debt. They do not establish detection of every real storage failure through the
void l4m_close API. The blocked-peer control is deliberately released; it does not
prove forced termination of a non-cooperative Go goroutine. XA/reset/admin session
lifecycles, Linux x86_64, Live, broad auth/prepared/consumer/fatal-wire semantics
and race freedom remain unqualified. Queue bounds are not total SQL/RSS bounds;
no benchmark or speedup is inferred.

## Reproduction and retention

Initial budget:2h active/tooling30min/heavy CI0 from2026-11-05 16:26UTC;
owned12GiB/free floor12GiB. Build/compile waiting is in the wall timeline, not
invented as separately measured active time. No heavy CI was submitted.

Extract these spike tools/templates to an owned workspace's temp/tools **before**
checking out the pinned guest/host commits. Build the guest at its source SHA with
scripts/build_generated_guest.py --development-output /exp/temp/artifact in the
same fixed builder/LLVM23 recipe as3C; require the guest hash above. Check out the
host SHA, run assemble.py --translate-only, inspect/require the recorded exact
binding (refresh_binding.py documents the complete-body review), then --resume.
The extra-control recompile changes only the named capture test file and records
its complete final staged inventory. Run wire.test -test.v -test.timeout=90s under
an external120s guard, then runtime_tests.py for the focused adapter boundary.
Historical prepare/refine helpers explain patch construction; the complete
committed guest/experimental.patch is authoritative, not the historical3C composer.

Raw observations remain in owned evidence; public copies normalize personal paths
and omit repeated build-receipt inventories. preservation.json records both hashes.
Useful source is retained in Git; SDK, downloads, converter/generated copies, WASM,
binaries, Go caches, container and worktree are disposable after verification.
