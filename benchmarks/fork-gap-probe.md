# Remaining Fork → first SQL attribution probe

Status: instrumentation prepared; new measurements await the focused CI run.
No latency improvement is claimed. The previous production-setting control is
[recorded here](fast-gap-after-aria.md); its Ubuntu ×1 total was 532/557 ms
p50/p95. This probe uses current main's production guest and configuration.

## Observable boundaries

The canonical Go runner still measures public Fork entry → connected client →
successful fixture COUNT. Its per-instance recorder now retains nested `fork`,
`api_startup`, `host`, and existing `guest` scopes:

- `fork`: entry, snapshot handle lock/preconditions satisfied, startup returned.
- `api_startup`: entry, options ready, native bundle resolved/verified, temporary
  runtime directory ready, host returned, Database ready, end.
- `host`: begin, native identity checked, snapshot validation complete, transfer
  directory ready, process spawn requested/returned, first ready frame header
  received, frame decoded/dispatched, response observed, guest ready accepted,
  wire listener ready, guest timing file read, end.
- `guest`: existing guest main, restore begin/end, MariaDB initialization
  begin/end, bootstrap complete, ready prepared.
- `caller`: API returned, client connected, first successful SQL.

The new transport timestamps use the host monotonic clock. They are recorded
by the reader and appended by the startup owner after channel delivery; no
concurrent writes to the trace and no new protocol messages are introduced.
They are enabled only for timing diagnostics, and ordinary SQL frames do not
collect timestamps. The frame-decoded marker includes pending-response lookup.

The public API spans native Resolve before host.StartVerified. Its elapsed
validation is now directly measured rather than guessed from the roughly 66 ms
outside-host residual. Host native identity checks and snapshot hashing are
separated. API host-return duration minus the nested host trace duration measures
identity-claim/diagnostic-output/return handoff; diagnostic JSON writing occurs
after the nested trace's end marker and remains inside the parent API span.
The fork scope also exposes snapshot-lock wait and the API-return handoff.

The roughly 66 ms outer residual and roughly 40 ms startup residual are
**disjoint nested-call regions**, by the synchronous source path: the former
is outside the host startup duration, the latter inside host spawn→ready.
This does not make their separately calculated medians additive. Each scope has
its own clock origin; compare durations, never subtract absolute offsets across
scopes. The JSON preserves raw per-instance timestamps and stage distributions.

## Blind spots and measurement

`cmd.Start()` return is the nearest available process-launch boundary, not the
instant the child first executes. The unmodified Wasmer CLI exposes no structured
AOT/runtime-initialized hook. Guest main is already recorded in the guest's own
monotonic clock, but its origin cannot be aligned with the host clock. Thus the
remaining spawn→ready duration residual includes pre-main runtime/WASIX/CRT work,
guest diagnostic publication and readiness delivery; it must not be labelled
pure Wasmer time. Ready-header receipt, frame decode and host response observation
now distinguish measurable transport/handoff cost. Startup waits on a response
channel rather than polling or sleeping. No polling interval was changed.

Dispatch `guest-build-boundary.yml` with `fork_gap_measurement=true` on the exact
pushed main SHA. Both macOS 15 arm64 and Ubuntu 24.04 x86_64 run 30 samples plus
two warmups, workers=1, 1,000 rows, existing guest-stage timings, no initialization
or expensive memory diagnostics. The existing verified WASM/AOT identity-reuse
path applies: no guest input changed in this probe. Raw results and stage tables
are `init-fork-gap.json` / `init-fork-gap.md` in the workflow's
`initialization-<platform>-<sha>` artifacts.

Existing runtime CPU samples and whole-runner CPU remain available with their
startup/exit precision and cleanup/sampling limitations. They do not establish
per-stage CPU. ×4/×8 should be added only if the ×1 result identifies a
concurrency-sensitive candidate. New p50/p95 and a result-based interpretation
must be filled in after CI completes; historical figures below are not the new
probe's results.

### Remaining latency candidates

1. **Native Resolve / API preparation:** the previous outer envelope was about
   50 ms macOS / 66 ms Ubuntu, but its allocation to native validation versus
   setup was unknown. Confidence in the envelope is high; confidence in a
   removable 30–50 ms portion is low. Scope: inspect the newly separated API
   boundaries. Risk: integrity must remain mandatory; no trust cache is proposed.
2. **Startup before observed readiness:** the previous duration residual was
   about 40 ms on both platforms. Confidence in the duration is high and
   attribution low. Scope: distinguish measured ready-frame/handoff time from
   still-unobserved pre-main work. Runtime changes carry higher risk and are not
   justified until attribution improves.
3. **Snapshot validation inside host startup:** the old combined validation span
   was 74 ms macOS / 105 ms Ubuntu. Its new split separates identity checks from
   snapshot integrity. Confidence in total size is high; removable cost remains
   unknown. Scope: integrity-preserving ordinary implementation work only.
   Risk: medium/high if validation ownership or mutation guarantees change.
