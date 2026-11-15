# Joined guest/transport stop before reclamation (#205)

Baseline source_commit: `b43541f5a5befc2f344284610ff17682434458f4`
(#203 ownership plus #204 Close operation). This is an isolated connected
candidate. Main integration, public API adoption and release remain undecided.
The later main difference at task start was project-status documentation only.

## Notification ordering

The production linked execution now uses StartInstanceWithStopped. Its first
channel reports execution quiescence and its second reports the full runtime
cleanup attempt. Existing StartInstance remains compatible. The runtime:

1. finishes the root and joins all guest workers, retaining their failure;
2. finishes requested snapshot freeze/export and every final output;
3. publishes the stopped result;
4. releases linear memory, descriptors and prepared mappings;
5. publishes the completed cleanup-attempt result.

A constructor failure reports stopped with its error. A worker that has not
joined prevents both stopped and memory release. The stopped event never
proves disposal. Original execution failure and later cleanup debt are separate.
The outer completion recovery remains; descriptor/mapping defers still run if
memory teardown unexpectedly panics, matching the previous separate defers.

The linked adapter consumes this event, marks the transport as stopping, closes
remaining endpoints, joins the response reader, then publishes Process's stopped
result. Only after runtime completion and transport retirement does it publish
exitErr and close Process.Done. Both producer entrypoints share this adapter with
controlled transports. A completed-only legacy fixture safely retires transport
after completion instead.

## Four pipe endpoints

| Endpoint | Owner and retirement |
| --- | --- |
| host input writer (`in`) | Process.closeInput; normal Shutdown may close it earlier, Abort and retirement share one sync.Once |
| guest input reader (`childIn`) | linked closePeer after runtime quiescence |
| guest output writer (`childOut`) | linked closePeer after runtime quiescence; last frames remain drainable |
| host output reader (`out`) | Process.closeOutput after reader join, or earlier Abort; shared sync.Once |

closePeer is invoked once by the lifecycle monitor. A known stopped runtime is
marked stopping before expected EOF; failures already recorded by Abort remain
retained. Output is not truncated to hurry a healthy reader. A reader that has
not joined prevents a successful transport stop notification.

## Host and Database handoff

Server.CloseWithStopped(ctx, notify) implements the exact #204 consumer contract.
It stops admission before starting a notification waiter. notify(nil) requires
Process.WaitStopped plus host session worker join. A stop failure/canceled wait
is reported as an error, not permission to reclaim a running guest. The method
continues ordinary synchronous finish/disposal and joins its notifier before
return. notify must not block. Server.Close delegates without a callback and
retains its synchronous contract.

Database's shared actor now receives the real notification instead of its
completed-only fallback. The existing Close still waits for the final attempt;
internal stopForCleanup can return earlier. Normal pending cleanup keeps its
Fork lease and does not mark the pool blocked. Actual cleanup debt and later
reclamation follow #203. No resource allowance, forced guest stop or connection
linger is introduced. The compile-time assertion in close_operation_test.go
prevents the real host signature silently losing this optional connection.

Snapshot/export keeps its existing acknowledgement, final-output and Done
boundaries. The early runtime event is emitted only after those outputs finish;
ordinary export callers still wait for full completion.

## Evidence and limits

Controlled tests gate worker exit, reader EOF and reclamation independently.
They check no early success, all four native pipe endpoints closed, once-only
peer retirement, construction failure, preserved trap result and host worker
join before notification. A final-export test buffers the acknowledgement in a native pipe while its
reader is gated: stopped must wait, then the reader drains the acknowledgement
before cleanup completion. This also passes under race instrumentation.
Existing startup cancellation/retained-owner and worker-failure tests remain enabled.

The actual-guest gated test uses the production constructor and engine, sets
innodb_fast_shutdown=2, then blocks the memory release closure. It observes a
successful stopped result and an extra active mapping while completed remains
pending. Opening the gate completes cleanup and restores the mapping count.
This is an injected release delay, not a real OS munmap failure or benchmark.

Reproduction (Go1.26.10):

```
go test -p 1 . ./mariamemtest ./internal/guest ./internal/host ./internal/generatedgo ./internal/forklimit ./internal/disposal
go test -p 1 -tags=integration ./tests/generatedmemory ./internal/generatedgo -run 'TestPureMemory32|TestProcessImageSurvivesIndependentRootsAndSnapshots|TestWorkerTrapActualGuestNotifiesAndIsolatesPeer|TestActualGuestStoppedBeforeMemoryRelease' -count=1
go test -race -p 1 -count=1 . ./internal/guest ./internal/host ./internal/generatedgo
```

Generated code, converter/guest bytes, static layout and license inputs are
unchanged from #203. All touched runtime files were already in the handwritten
installer ownership list; no generated hash refresh was required.

#206 must measure actual overlap and final-drain-inclusive cost. This work does
not establish a speedup, whole-suite resource acceptance, or another-platform
qualification. Use the connected branch as the common source for both arms,
including #203 fixes and #204 operation overhead in the synchronous baseline.
