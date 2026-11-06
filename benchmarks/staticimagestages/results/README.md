# Issue123: static-image Fork stage attribution

**Conclusion:** static-image reuse reduces Module initialization, but the increase
occurs mainly after guest execution begins, within the guest `server_init`
interval. The factory mutex is not the dominant cost in this cohort. Continue
with **one** candidate: file-map only initialized static-data pages and retain
anonymous backing elsewhere, keeping private writes, protection/grow and cleanup
contracts unchanged. Do not integrate the current whole-file prototype.

The strongest objection is that phase timing does not establish a page-fault or
CoW mechanism. The proposed change is a discriminating experiment, not a proven
fix; it could merely move cost or lose the prior RSS benefit. No fault counts,
PSS or new RSS observations were collected. The earlier performance rejection
remains unchanged.

## Results

Valid source: `9acfc1df04a990660350b65f3ceb2254116df290`. Unchanged guest SHA256:
`6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe`.
Mac M1 / 16 GiB / Go 1.27.3, one diagnostic binary for both arms.
Twelve valid processes, 576 children (`collected.json`; `attempt-summary.json` counts all 13 attempts); all SQL, cleanup, owner identity and per-child
elapsed partitions PASS. One additional incomplete recorder attempt (48 children,
SQL/cleanup PASS) is retained separately, excluded from comparison. Its outer-only
trace binding caused collection to stop; no runtime/guest fix was made.

The following **mean deltas** average all three equal-size pairs, so phases add
back to the Fork delta (rounding aside). This is diagnostic elapsed time, not
ordinary benchmark performance and not exclusive CPU usage.

| Non-overlapping elapsed phase | P1 image minus anonymous (ms/child) | P4 delta (ms/child) |
|---|---:|---:|
| before_memory | -0.0056 | +0.0031 |
| factory_lock_wait | +0.0002 | +0.1631 |
| map_and_protect | +0.6123 | -0.1469 |
| module_init | -1.6373 | -2.2144 |
| memory_other | -0.0015 | -0.0066 |
| handoff | -0.0023 | -0.0017 |
| execute_to_ready | +3.7365 | +9.8761 |
| ready_handling | -0.0234 | +0.1726 |
| diagnostic_finish | +0.0018 | +0.0396 |
| fork_total | +2.6805 | +7.8849 |

In every pair, Module initialization improves: P1 mean delta −1.59 to −1.70ms;
P4 −2.07 to −2.32ms. Execute-to-ready worsens in every pair: P1 +3.19 to +4.09ms;
P4 +8.88 to +10.44ms. Nested guest `server_init` explains where this occurs:
mean delta +3.75ms at P1, +9.77ms at P4. This nested interval is **not additive**
to the table. It includes elapsed execution/scheduling and does not isolate
InnoDB, the allocator, page faults or CPU contention.

Median-of-process child p50 Fork: P1 26.61→29.34ms, P4 35.34→40.69ms.
These independent medians do not add to median phase values. All process p50,
p95, means, maxima, every pair and every child are retained in `summary.json`.
No child lifecycle span or measured host/guest stage exceeded 100ms (0/576);
no tail exclusion. This cohort does not reproduce or resolve earlier SQL tails.

At P4 the image lock averages 0.163ms/child; median process p95 is 0.931ms,
maximum 3.244ms. Lock narrowing could help a little, but it is not the first
candidate for the observed 7.88ms mean Fork increase. At P1 lock cost is negligible;
mapping/protection adds about 0.612ms. P4 mapping differences do not show the same
pattern, so do not generalize the P1 mapping delta to a portable fixed cost.

Image creation costs 42.98ms (P1) / 44.99ms (P4) median, once in root Start.
Root Start medians are 37.63→95.43ms and 37.23→99.73ms respectively. Removing the
build scan is a separate root-start optimization; it does not explain warmed
Fork regression. All child traces confirm no image rebuild during Fork.

## One next experiment, not an implementation approval

Keep one prebuilt static image, but overlay only the initialized static-data
pages onto an otherwise anonymous reservation. Both arms must preserve the full
initial byte/global/drop-state equality, private writable pages, guard/grow
behavior, thread lifetime and joined cleanup. Record the actual mapped ranges
and same-source/guest identity. This isolates the effect of using file backing
for the zero-initialized/mutable part of memory without also changing factory
locking, initial-image creation or guest settings.

Use a bounded ordinary A/B for Fork/first-SELECT, full-suite wall/CPU and retained
RSS, with separate stage diagnostics. Fix its budget and decision threshold before
execution. Proceed to candidate adoption only on correctness plus the previously
agreed Fork-priority performance/guard criteria; otherwise stop or reject. This
campaign implements none of that follow-up.

pgmem is not evidence that a static-only mapping is already proven: its pinned
source also maps the whole file. Its initial image creation, logical size,
protection and lock policy differ. The follow-up tests a mariamem hypothesis,
not a claim that pgmem uses this exact strategy.


Diagnostic decomposition of the existing prototype, not a new performance or
adoption judgment. The prior ordinary campaign at `7ea413d3085da619fa6444228ba5f13d10154804`
remains the performance evidence: Fork regressed at P1 and P4 while held RSS fell.
This campaign changes observation only; image lifetime, factory lock scope,
full-file backing, constructor, SQL and cleanup behavior remain unchanged.

## Fixed scope and clocks

Mac arm64, Pipe, 1000 seed rows, 48 children, P1/P4, three alternating pairs per
cell (12 diagnostic processes). No ordinary campaign, pgmem rerun, guest rebuild,
Ubuntu, CI or adoption. Same binary for both arms; image route selected by an
environment switch. Every child retains its nested Fork/API/startup host traces and UNDO owner identity. A shared monotonic epoch aligns the nested traces.

The non-overlapping host elapsed-time partition is:

- Before memory: public Fork entry, capacity/admission, prepared handles and host setup.
- Factory lock wait: image route only; acquiring the existing constructor-wide mutex.
- Mapping/protection: mapping reservation and initial access enablement.
- Module initialization: anonymous generated initialization or image metadata restore.
- Memory other: remaining constructor bookkeeping, host imports and lifetime setup.
- Handoff: memory ready to guest execution entry.
- Execute to ready: guest execution, scheduling and ready transport, not exclusively InnoDB.
- Ready handling: decoded ready frame to timing trace end, including guest diagnostic read.
- Diagnostic finish: external Fork duration minus trace end, including trace serialization.

These sum to **each child's** measured Fork elapsed time. Independent medians do
not add; pairwise **means** are also supplied for additive attribution. Guest
server initialization and routine-schema intervals are nested diagnostics and
must not be added again. Initial image build is observed on root Start only.
At P4 elapsed time is not exclusive CPU cost. Tracing changes scheduling and
latency; compare arms within this diagnostic campaign, not directly to older
ordinary figures. No tail is removed. One initial collection attempt stopped after 48 children because the recorder retained only the outer Fork trace; it is preserved separately and excluded from the fixed valid matrix. This was an instrumentation failure, not a SQL or cleanup failure. RSS and page faults are not measured here.

## Reproduction

Use a fresh disposable workspace on the recorded source commit. Run
`python3 -B benchmarks/staticimagestages/build.py`, then
`python3 -B benchmarks/staticimagestages/run.py`. The build pins identity and guest
hash, runs affected observer/factory tests, and builds one diagnostic binary.
Both scripts enforce 8 GiB owned storage and 12 GiB free reserve. Each runtime
process has a 190-second deadline; no extra repetition is authorized.

Retained-data replay after cleanup:
`python3 -B analyze.py . --check` and `python3 -B check_analysis.py`.
`collect.py` consumes raw run outputs before cleanup; copy the collection/replay scripts from this bundle into the workspace evidence directory for reproduction.
They need only the retained observations and summaries, not temp/build inputs;
`--check` does not overwrite evidence. Source, overlay and binary hashes are in
`inputs.json`; `SHA256SUMS.json` covers the published bundle.
