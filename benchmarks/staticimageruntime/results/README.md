# Issue123 — real-engine static-image A/B

**Correctness PASS in the bounded local Mac profile; performance screen FAIL. Do not adopt this prototype for the Fork-time priority.** The image path reduced held-child RSS, but every one of five pairs at both P1 and P4 had a slower child Fork median. The regression is not explained only by initial image creation or a single long SQL tail.

Recommendation: keep the reusable-initial-state correctness finding and the memory result. If continuing this direction, first design a mapping that leaves heap/stack/other zero regions anonymous and privately file-maps only the initial data ranges. That is a new hypothesis, not a measured fix or authorization to integrate. Whole-engine reuse, settings changes and additional repetitions are not part of this result.

The strongest objection to rejecting the present shape is its consistent RSS reduction: about27.7MiB at four held children. That tradeoff may suit a different objective, but the Human's priority here is Fork elapsed time; the current path increased Fork elapsed and CPU. Image-cache ownership/API and Ubuntu acceptance remain unresolved.

## Frozen inputs and scope

- Tested source_commit `7ea413d3085da619fa6444228ba5f13d10154804` on experiment/static-image-runtime.
- Anonymous product basis `66f2fe9d4bbde9b20323e9ee9b1562f3af16b8a4`; constructor proof `85a714920baf99d1048ef95bc7d561db6034982c`.
- Same unchanged guest `6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe` / MariaDB12.3.3.
- macOS27.2 arm64 / Apple M1 /16GiB /Go1.27.3 /CGO0 /GOMAXPROCS8 /GOGC100 /Pipe.
- Both arms use the identical ordinary binary, selecting only the experimental initialization route. The anonymous arm uses the existing constructor through the same instrumented harness; it is not an untouched old release binary. Source identity/clean checkout, plan digest, binary hashes and Go VCS stamps are recorded in inputs.json.
-48 children,1000 integer seed rows, P1/P4, MaxForks=P,5 alternating pairs per cell. Separate held1/4-child processes also use5 alternating pairs. Each process builds its own image at first root Start. Suite timing includes root setup, seed/snapshot, batch, all child/snapshot/cache Close. Full lifecycle includes image-cache disposal.
-50 processes:20 primary,20 held-memory,2 positive SQL pilots,2 expected-negative controls,4 warmups,2 separate owner-diagnostic processes.1304 child acquisitions including2 deliberately failing controls. No added/replaced repetitions or removed tails. No CI, Ubuntu, native reference server, new pgmem measurement, guest regeneration, adoption or release.

## Timings and CPU

Values are medians of five process-level results. For Fork/first-SELECT/cleanup, first take the child median within each process. Percentages below are medians of the five paired percentage changes, not ratios of the displayed medians. All five values and changes are in summary.json. Independent phase medians are not additive.

|Metric|P1 anonymous|P1 image|paired change|P4 anonymous|P4 image|paired change|
|---|---:|---:|---:|---:|---:|---:|
|Fork child p50 ms|26.21|29.02|+10.73%|34.24|38.89|+14.23%|
|Fork child p95 ms|29.98|32.94|+11.47%|41.93|46.72|+8.17%|
|Fork through first SELECT p50 ms|26.62|29.48|+10.73%|35.25|39.67|+12.94%|
|48-child batch wall ms|1650.51|1720.20|+4.80%|581.79|628.05|+8.67%|
|Full suite wall ms|1695.87|1822.72|+8.32%|630.34|727.04|+16.39%|
|Full suite CPU ms|2505.49|2670.51|+6.93%|3216.70|3471.49|+6.36%|
|P1 process CPU during Fork p50 ms|36.52|41.85|+13.85%|—|—|not exclusive at P4|

Initial image construction median:37.06ms in P1 processes and35.43ms in P4. Root Start:33.81→91.60ms (P1),37.88→90.04ms (P4). The image setup cost therefore matters, but warmed child Fork and batch also regress. This does not establish a precise decomposition of the root-start difference or where inside the child engine startup the added time occurs.

P4 suite values (rep0..4): anonymous615.72/602.67/633.06/630.34/634.74ms; image992.68/708.37/736.78/717.31/727.04ms. The image rep0 COUNT/SUM on child5 took798.64ms and remains included. It is the only >100ms primary stage. Other four image P4 suites and all five child-Fork medians also regress; the conclusion does not depend solely on that tail. No #68 reopening or causal attribution of that untraced event.

## Separate memory observations

Current process RSS from ps, with equal explicit GC at each checkpoint. These are not timing runs, physical shared-page counts, PSS or system memory usage. Both total process RSS (including image effects) and pre-root/baseline deltas are preserved.

|Checkpoint|anonymous MiB|image MiB|paired change|
|---|---:|---:|---:|
|1 held, before child SQL|125.06|118.42|-5.25%|
|1 held, after child SQL|126.06|119.39|-5.27%|
|4 held, before child SQL|346.88|319.14|-7.99%|
|4 held, after child SQL|348.56|320.88|-7.92%|
|Increment per child after SQL, hold4|73.92|67.06|-9.28%|

Both hold counts improve total held RSS in all five pairs. The image uses one extra owned FD while cached (observed total FDs11→12 at hold1,26→27 at hold4). After cache Close, owned image FDs and active memory mapping/reserved/RW counters are0. Successfully closed DBs do not promise immediate RSS return to pre-root; after-child-Close RSS is also retained in summary.json.

## Correctness and screen

Both arms pass COUNT/SUM baseline checks, committed UPDATE/readback, repeated pristine children, subsequent SELECT, snapshot cap and disposal checks. Pilots additionally pass Unicode UCA comparison, DECIMAL, binary bytes, prepared SELECT and rollback. Corrupt-seed controls fail the exact pristine oracle and still dispose resources. These compare against the existing anonymous implementation, not a newly run native MariaDB reference or arbitrary SQL compatibility.

The changed factory also passes the constructor/mapping units from the prior proof. Observer units pass. Every process asserts actual selected route, image build count (image1/anonymous0), acquisition count, finite cap, empty scratch, no active mapping/RW/reservation/release failures, and closed cache with0 owned FDs.

The predeclared Fork screen (>=3% paired improvement and4/5 improving pairs at each P), first-SELECT, suite-wall and suite-CPU +5% guards all FAIL at both P. The +10% RSS guards PASS at both hold counts. This is a next-stage screening decision, not a release gate. Criteria are unchanged in plan.json; no threshold was revised after observing results.

## What changed and what is still a hypothesis

The normal constructor copies initial data and clears BSS into anonymous memory. The image prototype avoids repeating that initialization, but maps the **whole2GiB linear memory from a sparse file**, privately, retaining PROT_NONE and existing growth protection boundaries. Thus it changes backing for zero/heap/stack regions too, not only the9.61MB initial data. The existing generated guest remains unchanged and every DB still starts its engine.

Plausible costs include different file/zero-page faults, CoW behavior, mapping/protection work, and the prototype factory's serialized constructor section. None is isolated by this campaign. Do not claim that shared static data itself is inherently slower, that file faults are the proven cause, or that all the RSS reduction is physical sharing. Likewise the change includes avoiding the prior BSS clear, so gains/losses cannot be assigned exclusively to data-copy elimination.

A narrower static-range-only mapping may preserve the RSS benefit without changing the backing of the whole heap. It requires a new bounded design and ownership/protection validation, especially if replacing subranges of an existing reservation. It was not implemented here.

## Diagnostic evidence and reproduction

Separate P4 diagnostic processes record48 original per-instance owner traces per arm,96 total, no truncation. Child IDs exactly0..47 per arm and archive/member SHA256 are verified. Anonymous82680 events/image83779 events; maximum per child3134/2619. Logs retain who acquired/released the UNDO scope and waiting/notification events. Diagnostic timing is excluded from the primary results and cannot identify the cause of the separate ordinary798ms COUNT event. Full compressed traces remain in the owned compact evidence directory; owner-summary.json and archive-digests.json name and bind them.

Reproduce from the tested source above in a disposable experiment workspace: `python3 -B benchmarks/staticimageruntime/build.py`, then `python3 -B benchmarks/staticimageruntime/run.py`. Both scripts enforce source/guest/binary/plan identities and disk/time limits. Network access is needed to acquire the pinned SQL driver. The first sandboxed build failed only at driver download; ordinary-network-failure.log is retained. No DB process ran in that attempt. Build retry on the same source completed, then the fixed campaign ran once.

Recompute from these retained files without temp/build dependencies:
`python3 -B analyze.py . --check`

observations.json preserves all50 process reports in compact JSON; original-report-sha256.json binds original bytes and local original-process-reports.tar.gz preserves them with stderr. Summary replay is read-only. Fork medians were also recomputed independently from raw span endpoints and matched. Checksums are verified again after owned scratch/worktree cleanup. Report publication changes do not relabel the tested source.
