# Response-only Go pipe counterfactual (2026-11-16)

## Decision

Do not adopt this unbuffered io.Pipe prototype as a product optimization yet.
The response transport is causally responsible for much of the syscall CPU
profile, but removing that OS pipe mostly moves sampled cost to Go thread wakeups.
A stable whole-suite saving, or the approximately25ms required by the previous
10%-gap target, is not established by this noisy campaign. The bounded experiment
is complete; no extra performance repetitions or main changes were made.

The strongest positive evidence is GetOrder improving in all five AB pairs.
However, query AA also improved in all five pairs, with large excursions. Whole
suite AB improves in only three of five pairs, and its CPU effect is small. Neither
subtracting AA medians nor multiplying this result into the earlier comparison
would establish a current engine comparison or a guaranteed improvement.

## Fixed inputs and intervention

- Product source_commit: `6558ee8fb2211313a8aa0ea6070ac5256767811a` (PR217 merged).
- Measured experiment source_commit: `94123a47952b5550a67e8055be4be86f654ad255`;
  `scripts/git_identity.py inspect HEAD`, clean checkout before build.
- Harness copied from `experiment/modelcase-read-path`; original 70 assertions
  execute (`SKIP_READ_BODY=0`). SQL, SUM/audit triggers, MariaDB12 UPDATE OF status,
  interpolation, preaggregated revenue SQL, shared reader fork and MaxForks16 stay
  fixed. Synchronous Close and final cleanup remain included.
- Go1.27.4, CGO0, GOMAXPROCS8, GOGC100, macOS27.2.1 arm64. Not product Go1.26.10
  release qualification. `inputs.json` / `binary.json` bind source/environment/hash.
- Only response direction changes: `os.Pipe()` -> `io.Pipe()` in `startLinked`.
  Request direction retains OS pipe; guest Wasm/generated code and frame decoder
  unchanged. Same binary selects arms; observation wrappers/counters disabled for
  timing (shared dormant frame-counter check remains). No receive buffer, SQL
  omission, zero-Write elimination or other optimization was combined.

## Transport diagnosis (one process/arm, GetOrder4000 after fixture setup)

Both arms have identical request/frame and nonempty write-size histograms:
8,000 SELECT requests (2/order), plus one prepared-protocol opcode5 control
request observed in the measurement window. Do not describe this as precisely
SQL-only traffic with no other requests. 8,001 response frames; host writes
722,229 bytes, response stream6,271,607 bytes, equal at opposite endpoints.

| Measured io method calls | OS response pipe | Go response pipe |
|---|---:|---:|
| guest response Write | 16,002 | 16,002 |
| of which zero-length Write | 8,001 | 8,001 |
| host response Read | 16,002 | 24,003 |
| of which returns 0 bytes | 0 | 8,001 |
| host request Write | 8,001 | 8,001 |
| guest request Read | 16,002 | 16,002 |

Response nonempty writes are152–918 bytes, normally one complete frame/write.
Go io.Pipe exposes each empty Write as an extra zero-byte Read/handoff; it does
not remove that work. These are io method counters, not direct kernel syscall
counts. Counts are separate processes from all timed comparisons.

One additional CPU profile/arm (4000 GetOrder, setup outside profile):

| flat CPU sample | OS | Go |
|---|---:|---:|
| syscall.rawsyscalln | 0.74s /62.18% | 0.16s /13.91% |
| runtime.pthread_cond_signal | 0.20s /16.81% | 0.72s /62.61% |
| total sampled CPU | 1.19s | 1.15s |

This establishes a sampled cost shift, not elimination of all kernel work or
an engine-only wall-time decomposition. Each profile is short and sampled;
percentages/cumulative stacks cannot be added or treated as wall fractions.

## Fixed timing results

Each workload:2 warmups +5 AA pairs +5 AB pairs, interleaved seeded order and
alternating arm order. 44 timing processes total;22 full suites/1,540 test bodies.
No observations excluded. Profiles/counters are not mixed into timings.

| Paired metric (B/A) | median delta | median % | faster pairs | range % |
|---|---:|---:|---:|---:|
| GetOrder4000 AB | -73.160ms | -6.835% | 5/5 | -47.117..-4.443 |
| GetOrder4000 AA | -82.026ms | -4.517% | 5/5 | -34.006..-0.354 |
| P8 suite AB | -66.753ms | -10.223% | 3/5 | -23.035..+8.086 |
| P8 suite AA | -52.102ms | -8.301% | 4/5 | -23.718..+5.083 |
| P8 process CPU AB | -37.909ms | -1.449% | 3/5 | -3.203..+1.061 |
| P8 process CPU AA | +61.369ms | +2.249% | 2/5 | -3.517..+3.173 |

Independent AB medians: query1172.078 ->1065.193ms; suite625.141 ->609.137ms;
process wall666.224 ->667.546ms. These are not the paired-median statistic.
All per-process values, orders, CPU/process times and phase spans are retained in
`runs.json`, `summary.json`, and `campaign/`. The large AA variation prevents a
reproducible suite-speedup claim. This host session is appreciably slower than the
previous matched comparison: do not reuse its old comparison-arm time here.
No approximately69second Close observation recurred; its cause remains unresolved.

## Correctness and limits

- Entire internal/guest package PASS, including existing invalid greeting,
  worker failure, cancellation/disposal and stopped/reader-join fixtures.
- Added both-mode fragmented/empty/100KB transfer and close-unblocks-read/write
  checks PASS. Matched SQL semantics check PASS in both real-guest arms.
- All44 timing processes,2 diagnostic and2 profile probes PASS, with unchanged
  SQL assertions and checked normal Close. This is not full release acceptance.
- io.Pipe has no OS buffering: Write waits for consumption, empty Write adds a
  rendezvous, and closed-pipe error identity differs from os.File/syscall errors.
  Guest errno/error translation and all cancellation/crash/export interleavings
  have NOT been proven equivalent for product adoption. Existing controlled
  fixtures do not establish every real-guest fault behavior on both modes.
- macOS arm64 only. No Linux/Windows performance or product Go qualification.
- First attempt passed guest tests/build but failed baseline startup at localhost
  bind with sandbox permission denied, before any performance measurements.
  Original failure/identity retained in `sandbox-attempt/`; same fixed source
  rerun with permission outside sandbox, no code repair or favorable resampling.

## Recommendation and reproduction

Retain OS response pipe in product for now. A further, separately approved spike
would need to reduce rendezvous/wakeups rather than just exchange OS I/O for
unbuffered Go handshakes. The measured empty-write handoff is one concrete target;
its prior unadopted spike (#185 context) must be consulted before selecting it.
A bounded buffer would introduce separate backpressure/memory/error obligations.
No extra transport design or automatic follow-up campaign is started here.

Reproduce by preparing an experiment workspace on measured source, putting
`run.py` into its `evidence/`, and running it with `temp/`, `worktree/` siblings
under the documented workspace/disk guard (6GiB budget,8GiB free,1200s timeout).
Allow localhost bind. Runner builds the harness, verifies source, checks guest
and SQL semantics, diagnoses/profiles then executes the fixed campaign.
Run `analyze.py` on resulting evidence. `PLAN.md` is the pre-measurement protocol.

This evidence branch includes the disposable prototype and raw traces; do not
merge it wholesale or interpret it as a canonical product/provenance update.
