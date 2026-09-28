# Remaining Fork → first SQL attribution probe

Status: completed measurements from [CI run 36409990117](https://github.com/masahitojp/mariamem/actions/runs/36409990117).
No optimization or causal latency improvement is claimed. The previous production-setting control is
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
concurrency-sensitive candidate. The completed ×1 results below do not identify a polling or handoff delay
that would justify adding ×4/×8 in this attribution task.

## Completed measurement and identity

Measured host/harness commit: `80d922b037cfdcc5cd80ff2e2637c71591d38663`,
clean checkout, Go 1.26.8, Python 3.14.7, Wasmer 7.4.2, embedded MariaDB
13.1.0. macOS 15.7.9 arm64 and Ubuntu 24.04.5 x86_64 (SSE2+SSSE3 AOT).
Thirty samples after two warmups, 1,000 rows, ×1; no engine or restore changes.

The common WASM was **REUSED**, Ubuntu AOT **REUSED**, macOS AOT **REBUILT**
according to the completed workflow logs. Guest-producing source remains
`d44157adbc527da6482e205c176616489cb3ccbc`; AOT provenance's source field
identifies that guest source, not the newly measured host. The exact-input cache
verification ran before use. Local artifact inspection additionally verified every
WASM handoff file against `reuse.json`, both AOT manifest hashes against
provenance, and the common WASM/provenance identities across platforms.
AOT binaries are not included in the downloaded result artifact, so their bytes
cannot be independently rehashed from this result bundle.

- WASM: `41e3acfb51fe52ad13d9691de0bd3f05619266571e84dd1a0ddf263e082add7f`
- macOS AOT: `a74927f01e387f8d60fecb5e61a182e344b6a0d2b524d735817e5d632bcc6d4d`
- Ubuntu AOT: `e729fc07d7cb03de6b4bbf5334f0e1da460a8abfff56b0d3661b2688969e73fb`

Avoiding the guest rebuild explains the short CI path; it is distinct from
product latency. Raw JSON remains in the workflow artifacts, not committed.

## Measured Fork waterfall

Values are p50 / p95 milliseconds. Nested rows overlap; percentile columns
must not be added to reconstruct total latency.

| Boundary / duration | macOS | Ubuntu |
| --- | ---: | ---: |
| Fork → first successful SQL | 369.774 / 529.243 | 433.696 / 452.156 |
| API native Resolve / full bundle verification | 57.129 / 87.577 | 58.705 / 59.095 |
| Runtime directory preparation | 0.129 / 0.319 | 0.082 / 0.097 |
| API host handoff outside nested host trace | 0.156 / 11.711 | 0.094 / 0.112 |
| Host native identity metadata check | 0.009 / 0.022 | 0.012 / 0.014 |
| Host snapshot validation | 79.754 / 94.913 | 93.390 / 93.640 |
| Process spawn call | 1.368 / 4.526 | 0.310 / 0.387 |
| Spawn returned → ready header received | 219.693 / 302.762 | 274.523 / 291.407 |
| Guest restore | 107.041 / 146.967 | 172.135 / 177.692 |
| Guest MariaDB initialization | 63.626 / 114.101 | 68.263 / 84.207 |
| Guest bootstrap after initialization | 0.190 / 0.309 | 0.102 / 0.125 |
| Spawn → ready, outside recorded guest interval (derived per sample) | 43.233 / 62.478 | 33.871 / 35.629 |
| Ready header → decoded/dispatched | 0.058 / 0.112 | 0.052 / 0.067 |
| Decoded response → startup owner observes it | 0.015 / 0.038 | 0.012 / 0.016 |
| Ready accepted → wire listener ready | 0.059 / 0.105 | 0.068 / 0.076 |
| API return → client connection | 4.980 / 12.563 | 5.379 / 6.327 |
| Connected → first fixture SQL | 0.939 / 4.726 | 0.725 / 0.780 |

Fork snapshot-handle preconditions/locking are 0.002 / 0.003 ms macOS and
0.001 / 0.001 ms Ubuntu. There is no material measured lock delay at ×1.
The split resolves the former outside-host ~66 ms principally into **native
Resolve**, not a slow host handoff. The former ~40 ms spawn→ready residual is
inside host startup and remains separate from Resolve. Its ready-frame decode
and channel-delivery portion is very small; it does not establish which
pre-main runtime/CRT or diagnostic-publication work owns the rest.

**Source fact:** readiness uses a blocking reader and channel; there is no
startup polling interval or sleep to remove. **Measured fact:** transport decode,
channel handoff, listener creation and client connection cannot explain a
30–50 ms median gap in this run. **Unknown:** child first execution, AOT/runtime
initialization completion, and alignment of guest main with the host timeline.
The residual must not be called Wasmer CPU time or physical disk time.

## Start, CPU and historical comparison

| Start boundary | macOS p50 / p95 ms | Ubuntu p50 / p95 ms |
| --- | ---: | ---: |
| Start → first SQL | 323.961 / 352.880 | 228.991 / 244.412 |
| Native Resolve | 49.311 / 58.018 | 58.899 / 59.423 |
| MariaDB initialization | 216.857 / 238.309 | 123.983 / 133.688 |
| Outside recorded guest interval | 42.740 / 48.568 | 34.392 / 36.547 |
| Client connection | 4.931 / 8.213 | 8.764 / 13.522 |

Both Fork totals meet the exploratory ×1 500/750 ms KPI **in this run**.
Previous Ubuntu control was 532/557 ms, restore 223 ms, initialization 91 ms,
and snapshot validation 105 ms. Current values are lower across several existing
components, with no corresponding optimization. This is historical runner/cache
variation, not evidence that instrumentation solved the product gap. macOS tails
also remain variable. No new stable performance guarantee follows.

Fork sampled descendant CPU median is 0.230 s macOS and **0.000 s Ubuntu**.
The Ubuntu `ps` samples have insufficient CPU resolution at this duration;
zero does not mean no runtime CPU was consumed. Runner CPU medians are 0.140 s
and 0.163 s respectively, including measurement/cleanup work in their existing
interval. They cannot be combined into accurate startup CPU accounting or
attributed to the new stages. Sampled descendant RSS medians are 339.3 / 401.4
MiB; they are secondary observations, not private/incremental-memory KPIs.
No expensive memory diagnostics were run.

### Remaining latency candidates

1. **Native bundle Resolve:** 57/59 ms median macOS/Ubuntu. Attribution
   confidence high; removable 30–50 ms portion unproven. Scope: integrity-preserving
   verification implementation investigation, without another trust cache.
   Risk: high if mandatory byte/hash checks or mutation handling are weakened.
2. **Snapshot integrity validation:** 80/93 ms median. Attribution confidence
   high; possible savings unknown. Scope: inspect ordinary validation CPU/read
   work while retaining every inventory/content check. Risk: medium/high;
   snapshot trust and mutation semantics must remain unchanged.
3. **Unobserved startup envelope:** 43/34 ms median. Duration confidence high,
   cause confidence low. Scope: a narrowly supported runtime/CRT initialization
   boundary, if available; ready decode/channel optimization is not justified.
   Risk: higher maintenance if runtime modifications are required. Even removing
   the whole residual is only a derived bound, not demonstrated feasibility.

Restore remains the largest individual known interval on Ubuntu; it is outside
this remaining-gap attribution task. No optimization is selected or implemented.
