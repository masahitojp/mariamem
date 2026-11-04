# Why pgmem Fork is cheap: source contrasts and MariaDB init stages

2026-11-04. **The new observation changes the priority: about17ms is spent before
MariaDB starts server components/plugins; the InnoDB plugin costs about9.3ms,
and direct buffer-pool creation about1.2ms.** It is no longer justified to treat
the whole roughly34ms server-init interval as InnoDB or buffer-pool work.

Recommend narrowing the next timing question to the early embedded-server path:
timer calibration versus common variables/options/SQL setup. Keep Issue88's16/8MiB
comparison as a separate small buffer/RSS hypothesis, with no expectation that
halving the pool alone removes tens of milliseconds. The strongest limitation is
that this early17ms still contains several functions; no safe removal or caching
strategy has been demonstrated. This bounded observation ends here.

## Matched observations

Pinned mariamem source_commit `bc00b8e66e5fd57bc9b2127001faf8e05952b417`, the same
source as the [complete-suite comparison](https://github.com/masahitojp/mariamem/blob/00cbd7799176409fbb0be2a608940f4e9d5a2843/benchmarks/lifecycle-full.md).
Guest SHA256 `96129c76872ab0891329e8e356233d691208195654e878a2853139901712d05f`.
Measured harness_source_commit and actual executable VCS stamp:
`ce921fb4` (full SHA in [inputs](forkinitdeep/results/inputs.json)), clean clone,
modified=false. git_identity.py checks commit objects and the benchmark-only diff
before build; the Go observation overlay and all preimage hashes are explicit.

Apple M1/16GiB/macOS27.2 arm64, Go1.27.3,CGO0,GOMAXPROCS8. Same1,000 integer rows,
explicit Snapshot cap1, root closed before four serial children per process.
Three alternating control/init fresh-process pairs, one separate warmup per mode,
one positive init pilot and one wrong-seed negative. No extra primary repeats.

The same binary runs both modes. Both use existing guest startup timing and the
previously checked runtime observer/guest-JSON reader. Only init mode supplies
MARIAMEM_INIT_DIAGNOSTICS to activate already compiled engine/plugin markers and
allocation/I/O counters. No guest rebuild, parser, engine option, synchronization
or timer policy changes. Initial preparation is not counted as a child Fork.

| Time, ms: child median per process → median of3 processes | Control | Init diagnostics |
| --- | ---: | ---: |
| Public Fork wall |34.969|36.169|
| Public Fork process CPU, all threads |47.601|49.447|
| server_init begin→complete |31.152|31.655|

Paired init/control Fork-wall differences are+4.57%,−0.10%,+6.84%. Diagnostics
have measurable overhead and change scheduling; no speedup/equivalence is claimed.
The earlier approximately34ms server-init observation is a separate cohort, not
an optimization baseline. Substage times below are descriptive elapsed durations
with diagnostics, not per-stage CPU or guaranteed removable work.

## Inside server initialization

| Diagnostic interval | Median ms | Relation |
| --- | ---: | --- |
| **Embedded entry→before server components/plugins** |**16.961**|Primary next target|
| Components before plugin init |1.223|Includes MyISAM key-cache initialization1.163ms|
| All plugin initialization |12.289|Contains the next four rows|
| ↳ InnoDB plugin |9.280|Contains its buffer/recovery intervals|
| ↳ InnoDB buffer-pool create |1.198|Nested; not an additional cost|
| ↳ Aria plugin |1.381|Nested in plugins|
| ↳ caching_sha2_password plugin |0.587|Nested in plugins|
| After plugins→embedded complete |0.920|Final common setup|
| Complete embedded interval |31.464|Nested within server_init31.655ms|

The InnoDB runtime subinterval is9.229ms. Within it, the interval from
memory/background setup completion to open/recovery completion is6.464ms. That
label covers the source between existing anchors, not pure physical disk I/O.
Each column is independently reduced, so percentile/median rows are not added.
All init records contain168 events/child with dropped_records=0. Guest process
and thread CPU counters are null/unavailable, not zero; only host whole-Fork CPU
is used. Requested allocation counters and linear-memory size are not RSS.

During the early common interval, the wrapped read/write byte counters and
successful pthread-create counter do not advance in any observed child. The
wrappers do not intercept every libc-internal call, nor prove that no scheduling
or other syscall cost exists. This does locate the17ms before the later InnoDB
worker/recovery path; Issue68's post-ready SQL queue wait is not its attribution.

### What the early interval actually contains

The marker called embedded_options_complete is inserted immediately before
init_server_components(), after a collection of operations. It does **not** mean
17ms of command-line parsing. The pinned
[embedded-server source](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/lib_sql.cc#L532)
includes thread-local setup, early variables/defaults/system-variable registration,
my_timer_init(), init_common_variables() and the init_ssl() call.

[init_common_variables](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/mysqld.cc#L4097)
sets up type handlers, variables, thread support, timezone/locale, option-dependent
limits, error messages and SQL registries. Individual costs remain unmeasured.
Two apparent suspects are excluded by source guards: init_libstrings() and
init_ssl() do no work in this embedded build. Auth-key plugin cost is separately
observed at0.59ms; it does not explain the whole early interval.

[my_timer_init](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/mysys/my_rdtsc.c#L363)
contains overhead/resolution/frequency calibration loops. It is a concrete timing
target, not a proven17ms cause: which timer branches run and their actual cost
were not separately measured. Do not disable it or cache sys_timer_info based
only on this source reading.

## What the pinned pgmem path does differently

Source audit is pinned to v1.18.2 commit
`a61005d37d01e6671f814fe8ca828222e8147df4`. All fetched file hashes/URLs are in
[source-audit.json](forkinitdeep/results/source-audit.json).

1. **Fresh has substantial work that Fork skips.**
   [Start](https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/pgmem.go#L98)
   creates a base filesystem, expands compressed share/data archives, optionally
   runs standalone PostgreSQL to create the requested role/database, calls
   debug.FreeOSMemory(), then starts the cluster. The prior comparison requested
   Database=test, so that optional CREATE DATABASE path is included. These are
   not default-postgres-database Fresh measurements. Exact milliseconds of each
   operation remain unmeasured; Fresh's extra cost is not all PostgreSQL boot.
   The source comment mentioning initdb is less precise than this actual body,
   which expands a prebuilt data-directory archive.
2. **Fork copies filesystem metadata and starts a new postmaster.**
   [Fork](https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/snapshot.go#L97)
   reuses the Engine, clones a COW filesystem view and calls boot. File contents
   stay shared until writes. It does not clone a live, fully initialized database
   process. MariaDB also attaches saved handles cheaply (earlier0.05ms), so a
   hypothetical bulk-file-copy difference cannot explain tens of milliseconds.
3. **Shared initial data and memory strategy.**
   The [AOT factory](https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/internal/aot/aot.go#L37)
   maps an initial-data image COW, runs constructors per instance and uses a
   lazily materialized address reservation. This applies to both Fresh and Fork.
   It is a real host implementation contrast, but MariaDB's initial module
   construction is only about1.5ms in prior observation. Sharing that construction
   alone is not an explanation or demonstrated cure for the remaining30ms gap.
4. **Different readiness boundaries, with a measured bound on the explanation.**
   [StartCluster](https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/internal/engine/cluster.go#L47)
   waits for postmaster readiness. A SQL backend is started for a connection.
   MariaDB finishes embedded storage-engine/plugin initialization and its bootstrap
   connection before returning. However, re-reduction of the prior same-cohort
   serial results gives Fork→successful SELECT1 **40.03ms mariamem /9.39ms pgmem**.
   Deferred connection work narrows but does not eliminate the gap. This is not
   a new pgmem timing run.
5. **Close has a materially different completion policy.**
   [pgmem Kill](https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/internal/engine/cluster.go#L212)
   deliberately discards the cluster without graceful checkpoint, waits for
   process completion and starts segment cleanup asynchronously. Process Done
   is signaled before module unmapping in exec's defer. MariaDB joins guest
   workers and releases owned mappings before reporting complete disposal/returning
   its lease. This helps explain why tiny Close API times are not measurements
   of the same resource-completion boundary. It is not a safe proposal to skip
   MariaDB cleanup or silently change the Fork cap contract.

pgmem also defaults io_method=sync to avoid three PostgreSQL I/O workers; MariaDB
uses simulated AIO with its configured background work. Both have background
processes/workers. Source differences alone do not quantify their timing contribution.

## Decision supported now and next bounded question

The previous explanation is now sharper: pgmem Fork skips its Fresh-only setup,
and its prepared postmaster path has little upfront work in this fixture.
MariaDB repeats a substantial **common initialization path before InnoDB**, in
addition to InnoDB startup. The largest observed target is the17ms common path.
The cause inside that path, the matching PostgreSQL function-by-function cost,
and a safe way to remove/reuse it remain unknown. Do not label it unavoidable
MariaDB overhead or promise a5ms Fork.

Next bounded work should split my_timer_init() from init_common_variables()
and the preceding setup. Existing hooks do not split those calls. First assess
whether the exact generated callsites can be identified for a small Go observation
overlay (initial30-minute tooling cap); if not, additional C timing points require
a guest rebuild, which must be budgeted separately before proceeding. Prior guest
build elapsed time was about17minutes, before conversion/validation. No such build
or optimization is started by this report.

For Issue88, the direct create interval is about1.2ms, not17–34ms. Buffer size
can also affect later cache/recovery work and SQL, so1.2ms is not a strict bound
on every downstream change. It does make a large startup-speed expectation from
that setting alone unsupported; retaining the RSS question remains reasonable.

## Verification, reproduction and cleanup

Six primary processes/24 children, two warmups/eight children and a positive
pilot/four children pass SQL, pristine baseline/independent update and cleanup.
The negative pilot fails the expected seed oracle and cleans its child. All10
processes end with empty scratch, zero active mappings/RW/reserved bytes and no
release failures. Strict reduction checks actual dropped_records=0 throughout;
a runner follow-up corrects its drop-key check without relabelling the measured
harness or rerunning primary trials.

The compact format stores a shared column list for every initialization event;
its unpacked10 records equal the originals exactly, including all counters and
plugin events. Plugin names may repeat, so begin/end events are paired by ordered
stacks rather than overwritten in a name dictionary. Three mutations reject a
missing boundary, a dropped record and a hidden SQL failure.

```sh
python3 benchmarks/forkinitdeep/analyze.py --results benchmarks/forkinitdeep/results --check
```

This read-only check needs no build/temp data. [Compact](forkinitdeep/results/compact.json),
[summary](forkinitdeep/results/summary.json), [assessment](forkinitdeep/results/assessment.json),
[checksums](forkinitdeep/results/SHA256SUMS.json). Reproduction: use a new disposable
workspace with7GiB budget/16GiB free reserve; clone exact measured harness into
temp/source, copy its run.py to evidence, set MARIAMEM_EXPERIMENT_TEMP/EVIDENCE,
and run `python3 evidence/run.py --phase all` under experiment_disk.py with a
1200-second deadline. Use the corrected runner drop-key guard or the strict
reducer before accepting results; keep actual new source/binary hashes.

No product/API/guest/generated/release modification, hosted CI, Linux acceptance,
RSS claim or adoption decision is included. Requested allocation bytes and
logical guest-memory size are not resident/private memory. The experiment ends
at attribution and the source comparison; useful compact evidence is pushed,
owned clones/binaries/caches are disposable.
