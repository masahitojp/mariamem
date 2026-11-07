# CRC-adopted main versus pgmem: finite lifecycle refresh

**mariamem Fork completes this 48-case P4 workload in455.3ms median,
versus pgmem345.9ms (1.32×).** Within mariamem, Fork is19.8% shorter than
Fresh atP4 and25.3% shorter atP1. This is a new single-Mac cohort, not a
paired before/after CRC experiment. It does not measure the proposed lexer-map
optimization from Issue126; no new optimization is present here.

[Interactive chart](report.html) · [Summary](summary.json) · [Every child](children.csv)

## Fixed inputs and scope

- Product main source_commit: 3d8b2201c1f36fa5b7264e0450104055f3822272 (CRC PR125 adopted).
- Harness source_commit: 3e636a7f41339e3f68ca360356337342b6ffdbc9; no product changes relative to that main. Source clean before build/run. Recipes in parent directory; immutable premeasurement plan at that commit.
- MariaDB guest SHA256: 6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe.
- pgmem v1.18.2 source_commit: a61005d37d01e6671f814fe8ca828222e8147df4; annotated tag_object_sha: 145e5d2fc70983b89a4bdd8438e547fcd60244ed. Identity validated with git_identity.py.
- Go1.27.3, CGO0, GOMAXPROCS8, GOGC100; Pipe/no TCP; mysql driver1.9.3 and pgx5.11.0. AppleM1/16GiB, exact OS in host.json. Binary hashes/build info in inputs.json.
- Identical integer workload,1000 seed rows,48 independent cases; Fresh/Fork × P1/P4, five adjacent product pairs per cell. Product order alternates and cell order rotates. max_forks equals P and actual getters are asserted.
- 8 positive/negative pilot processes,8 warmups,40 primary processes,2 separate mariamem UNDO diagnostic processes:58 processes,2412 attempted children;1920 primary children. No replacement, extra repetitions or outlier omission.
- SQL pristine/updated row oracles, child isolation, exact sample/spans, resource cleanup and owned temp cleanup pass. Wrong-seed controls fail for the intended oracle. All96 diagnostic traces are untruncated. Six analysis tests and read-only replay pass.
- Build/download excluded. API suite runs from first Start through final Close, including seed/preparation/capture and all child work. External process wall starts after disk preflight and ends at process exit. CPU is cumulative across threads.

Human authorized measurement after a host-contention warning. The previously
busy Docker container had stopped at campaign start (host-load-before.txt is
empty). A spot check during the run still observed VM37.6% and two Spotlight
workers18.9% CPU each, plus desktop activity. This is not an isolated host or a
continuous load census. No other owner's workloads were stopped.

## Full suite: medians of five processes, milliseconds

|Mode / parallel|mariamem wall|pgmem wall|mariamem CPU|pgmem CPU|
|---|---:|---:|---:|---:|
|Fresh P1|1640.9|3300.3|2556.6|5418.2|
|Fresh P4|567.8|1544.1|3164.0|8006.9|
|Fork P1|1225.4|612.9|1749.0|876.6|
|Fork P4|455.3|345.9|2188.4|1287.9|

Fork P4 suite ranges: mariamem452.8–1130.3ms; pgmem317.6–445.8ms.
A single mariamem primary count_sum took802.10ms (rep3, child30), making
that suite1130.31ms. There were no other primary SQL spans>100ms in either
product. All observations, including this case, contribute to the reported
statistics. The primary comparison does not identify its internal wait owner.

P4 spawn-to-exit wall medians: Fork513.6/403.8ms and Fresh607.8/1675.3ms
(mariamem/pgmem). The older cohort's erroneous disk-preflight-inclusive
external wall is not used. This metric still does not turn pgmem process exit
into proof that every asynchronous cleanup operation completed.

## Per-child phases: median of each process's median, milliseconds

|Phase|mariamem P1|pgmem P1|mariamem P4|pgmem P4|
|---|---:|---:|---:|---:|
|Fork API|20.36|5.07|26.30|9.97|
|Connect|0.29|2.72|0.44|5.33|
|COUNT/SUM|1.08|0.51|1.30|0.80|
|UPDATE|0.21|1.81|0.27|3.12|
|Connection retirement|0.05|0.01|0.07|0.01|
|Close|1.76|0.08|3.69|0.13|

Fork API remains the largest per-child difference:16.33ms atP4. It is
partly offset by faster connection and UPDATE paths; adding independent
medians is not a critical-path reconstruction. mariamem Fork API grows29.2%
fromP1 toP4, while its complete suite shrinks62.8%; this run does not show a
P4 scaling ceiling. NoP8 claim is made.

The Close contracts differ: mariamem waits for worker completion and mapping
disposal; pgmem signals completion before all module unmapping and frees some
segments asynchronously. API return and process exit are not equivalent proof
of completed cleanup. Do not describe the Close difference as equivalent work
removed. Lifetime peak RSS is retained in raw reports but is not per-child
retained memory and is not used to claim an RSS improvement.

## Separate UNDO diagnostic

Two extra mariamemP4 runs, Fresh/Fork48children each, retain the existing
owner/relay instrumentation. They are excluded from primary timing.
diagnostics.json and the lossless trace archive record25984purge scopes,
0purge aborts,0query rseg waits,432background page waits and0matching
query→purge→page wait chains. Maximum3959events/child; no truncation.

The diagnostic Fork run also had a count_sum span804.49ms (child12),
but no UPDATE span>100ms (maximum2.20ms). This does not establish that
count_sum's delay is the previously observed UPDATE/rseg mechanism, and does
not close Issue68. The query-side observer is not general lock ownership
tracing for arbitrary SELECT waits.

## Interpretation and next decision

The old UCA-era cohort on66f2fe9d reported ForkP4 suite707.5/372.7ms
(mariamem/pgmem), ratio1.90×. This cohort gives455.3/345.9ms, ratio1.32×.
These are historical context, not paired CRC effect estimates: host state and
sampling differ, and pgmem also changed in observed time despite a fixed source.
Use the already accepted CRC paired experiment for its causal claim.

The remaining Fork cost justifies looking at a specific common-init candidate,
but this lifecycle test cannot assign that cost to lexer maps. The next bounded
question is invocation count, unique512-byte map pairs and exclusive
init_state_maps time on current main. Only if material should the proposed
prepared-map prototype proceed; otherwise defer it and revisit Issue88. No
broad initialization cloning, product default, guest source or API change was
made or adopted in this task. Candidate adoption and release remain separate.

## Reproduction and retained evidence

From this directory, with no build tree or native dependencies:

    python3 analyze.py --check
    python3 diagnose.py --check --archive /path/to/undo-traces.tar.gz
    python3 -m unittest test_analysis test_undo

analyze.py reconstructs the full40-process/1920-child summary and CSV from
observations.json in the repository. diagnose.py additionally requires the
external undo-traces.tar.gz archive and verifies its pinned checksum before
replaying all96traces. That archive and raw-processes.tar.gz are retained in
the owned local evidence/published directory; they are not in Git (public-source
policy excludes binary archives). A fresh clone alone can replay all timing
results but cannot independently replay the raw UNDO traces. diagnostics.json
preserves their analyzed results; archive-digests.json pins the originals.
Original numeric values are unchanged. Temporary source, binaries and caches
are disposable after publishing. This report is on an experiment branch;
no automatic main merge is authorized.

For new measurements, use the pinned harness commit, acquire pinned pgmem in
the workspace temp directory, and run build.py then run.py per plan.json with
the disk guard. Fresh measurements will differ; the saved replay is the exact
reproducibility check for this cohort. Original archives contain no build-tree
paths and inputs.json normalizes workspace paths to <WORKSPACE>.
