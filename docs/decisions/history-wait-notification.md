# Notify the pool while history_size waits on a rollback-segment reader lock

The Human adopted the narrow native candidate for canonical integration and
acceptance on 2026-11-29. This decision authorizes preparation and correctness
verification; it does not assert that the intermittent long wait is resolved
and does not authorize a release.

The goal remains shorter completion of the whole parallel suite. Natural
diagnostic evidence showed another thread's queued WRITE waiting while purge
held the rollback-segment writer lock and the coordinator blocked on a reader
lock without notifying the pool. Recovery followed pool maintenance. This
supports correcting the missing notification, rather than changing its 400ms
timer. The observation does not establish the cause of every long benchmark
sample or all of the Ubuntu/macOS performance difference.

`history_size` first tries the supported native reader-lock API. Only a failed
try enters an ownership-bearing scoped notification around the blocking lock.
The generic pool inspects native worker TLS/state under its mutex, skipping
nonworkers, inactive/long tasks and existing waits. Begin failure rolls back
new ownership; scope exit ends only its own wait. Existing wait APIs, lock
ordering and the final unlock loop remain unchanged. Other pool types retain
the default unsupported no-op; the WASI guest uses the generic implementation
on both product platforms.

This adds native API/slowpath maintenance in four upstream files. Future guest
updates must recheck that API and rerun its native contract tests. Existing
allocator/CRC and actual dictionary-regression bindings remain exact full-body
and data checks; update effort beyond this candidate is not measured. No
private-offset Go runtime helper, scheduling gate or experimental whitelist is
part of the product. Canonical preparation records all four modified files.

The prior fixed normal comparison was 20 full P8 processes per arm, 2800 case
bodies, all passing. Whole-process medians were main 512.547 / candidate 522.200 ms;
the balanced block geometric difference was candidate +0.836%. Neither arm had
a sample >=400ms (0/420 each). These data establish neither an ordinary speedup
nor tail removal. Rebuilt guest layout and shared-host conditions also prevent
attributing small differences uniquely to the notification. Do not add unguided
sampling or require a successful scheduling-gate reproducer for this adoption.

Canonical acceptance requires two fresh source-to-Wasm builds, exact guest/link
identity, independent byte-identical Go regeneration, current daily checks and
full relevant integration on Linux amd64 and macOS arm64. This includes actual
dictionary contention, worker failure/reclamation, memory32 traps, SQL,
Snapshot/Fork and normal Close. Retained-function attribution is re-audited for
the new guest, preserving previous audit identities as historical facts.
Acceptance belongs to the exact-source CI receipts, not provisional bootstrap
metadata. The previous UNQUALIFIED single guest is a preparation input only.

The bounded preparation/acceptance task allows 120min active work, 30min of
measurement tooling and at most 2 heavy CI submissions. It adds no benchmark
campaign. On unresolved failure or budget exhaustion, preserve the candidate
and finite evidence and report the missing work/cost; do not weaken existing
failure oracles. Main integration review and later release approval remain
separate decisions.

Prior candidate/evidence recipe:
`974b55b7d981a37e30d8e52198113ce10119cf5f`,
`benchmarks/wait-notify-candidate/README.md`. The baseline is
`e00b3ec41f9c5d4ca3f85db4ff73198dbf3613e9`; the guest hash is
`e6d0570841d79b82cfee1a87070080febeb08da6dba1727c5341e53ae6463c9b`.
