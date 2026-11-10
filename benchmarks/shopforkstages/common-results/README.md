# Common startup attribution: current Pipe shop70, P4/P8

**The three initially selected candidates do not dominate common startup.**
Timer characterization is the largest of those candidates at0.936/0.959ms
(P4/P8 child medians). Locale plus lexer literal lengths cost0.306/0.323ms;
SQL-function plus JSON lookups cost0.272/0.289ms. Charset initialization is
2.059/2.143ms, and the subsequent interval to common completion is2.470/2.544ms.

Recommendation: do not undertake a broad fixed-lookup/locale rewrite for this
workload. The smallest next decision is whether a bounded timer-consumer audit
can justify avoiding per-Fork calibration; about1ms of observed median time is
in scope, not a promised saving. For a larger common-startup target, investigate
charset initialization and its following selection/finalization interval next.
Do not equate the latter with a single charset function or automatically share
mutable registries. No optimization prototype or product adoption is made here.

The strongest limitation is observer disturbance and one shared Mac. ON adds
2.0–4.0ms to paired process Fork medians atP4 and0.9–9.3ms atP8. These are observed
elapsed regions, including scheduling; they are not exclusive CPU costs or
fractions to apply to the OFF Fork. Nevertheless all five candidate regions and
the charset region were present, ordered, and non-overlapping in every observed
root and child. The remaining time is retained, not assigned to a favored theory.

## Fixed inputs and exact observation boundary

- Product source_commit: `b1218737ffa0bc1d08e9b1285b9bcf6ccf8adc50`.
- Measured harness source_commit: `d675bc07f9dacdadd7f82b77e757159670271d2c`.
- Guest SHA256: `8e3761eaf65df842191c98cfc4bf493ae08df9374204774f453b9349e21711df`.
- Go1.27.3, CGO0, Apple M1/16GiB, macOS27.2; GOMAXPROCS8/GOGC100.
- Same shop70 workload:50 reads sharing one prepared child plus20 private write
  children =21 Forks/process; P4 cap5 / P8 cap9; Pipe,16MiB/read1 unchanged.
- Three primary OFF/ON pairs per parallelism and one warmup per cell:16 processes,
  1120 test cases total,840 primary. Each primary cell has63 child Forks.
- Rotate parallelism and OFF/ON order. Retain all slow cases; no retries.

The original [source audit](https://github.com/masahitojp/mariamem/blob/8d7ffa560a3734d17542ee034552f53976d9ad2f/benchmarks/commoninitcurrent/README.md)
identified the candidates but did not measure their individual costs.
The previous [whole-Fork stage report](https://github.com/masahitojp/mariamem/tree/7ebc279e4c8ed2a25dbf7e54f9c93e14238f8b2c/benchmarks/shopforkstages/results)
remains bound to its own source and cohort. Its common7.65/10.23ms values are not
controls proving a speedup in this new6.75/7.53ms cohort. No performance treatment
was applied.

## Measured regions (milliseconds)

| Region | P4 p50 | P4 p95 | P4 mean | P8 p50 | P8 p95 | P8 mean |
|---|---:|---:|---:|---:|---:|---:|
|timer|0.936|4.710|1.512|0.959|4.535|1.669|
|locale|0.266|0.291|0.275|0.282|0.765|0.625|
|lex|0.037|0.047|0.039|0.042|0.090|0.053|
|functions|0.249|0.274|0.266|0.265|0.832|0.386|
|json|0.023|0.026|0.025|0.024|0.070|0.034|
|charset_inclusive|2.059|3.405|2.233|2.143|6.533|2.996|
|other_excluding_charset|2.898|3.643|3.137|3.025|7.851|3.840|
|total|6.746|11.347|7.488|7.528|17.513|9.601|

The first seven rows partition each child's `total` exactly, so their **means**
add. Medians/p95 do not add. Charset is excluded from the residual row: it is not
counted twice. Its inclusive entry/return interval lies wholly within common and
outside the five initial candidate intervals in every accepted trace.
`other_excluding_charset` includes the following disjoint remainder locations;
most of it is after charset initialization:

| Region | P4 p50 | P4 p95 | P4 mean | P8 p50 | P8 p95 | P8 mean |
|---|---:|---:|---:|---:|---:|---:|
|before_timer|0.244|0.458|0.269|0.257|1.258|0.435|
|between_timer_locale|0.016|0.025|0.017|0.018|0.096|0.036|
|between_locale_lex|0.154|0.183|0.162|0.167|0.641|0.288|
|between_json_charset|0.001|0.002|0.001|0.002|0.003|0.002|
|after_charset|2.470|3.251|2.685|2.544|6.633|3.076|

Tiny gaps between lex/functions and functions/JSON are retained in the residual
rather than silently assigned. `after_charset` is an enclosing elapsed interval,
not a measured exclusive function. In pinned MariaDB it can include returning
from charset lookup, selected collation lazy setup, filesystem charset/locale
selection, cache/path work and filesystem case-sensitivity handling, then the
remaining embedded options/SSL/umask path. This run cannot split those costs.

Every common region and whole Fork has zero >100ms primary children. The largest
P8 common region is still included in summary.json. Tail-sensitive comparisons
should use these child distributions and per-process values, not just means.

## Timer finding and implications

Every primary child reports cycles unavailable (all four cycle fields zero).
Observed routines/frequencies: nanoseconds CLOCK_GETTIME/1e9, microseconds
GETTIMEOFDAY/1e6, milliseconds CLOCK_GETTIME/1000, ticks TIMES/100. These are the
actual20 fields of `sys_timer_info` read immediately after the pinned timer
region, not the native Mac's timer assumptions. Full observed combinations are
in summary.json, and all20 values per startup survive in observations.

Because cycles are unavailable, the upstream cycle-dependent frequency probes
are not the explanation for this cost. The millisecond resolution probe waits
until it observes a clock step; about1ms timing is consistent with it plus the
other probes. This does **not** isolate that particular loop: timer p95 is4.71ms
atP4 and4.54ms atP8, and elapsed includes preemption. No per-clock-call logging
was added. A follow-up must check all consumers and exact clock semantics before
replacing calibration; do not zero the metadata or skip actual timekeeping.

Locale/lex lengths and SQL/JSON lookup construction are real repeat work, but
small typical costs here. Both combined candidates are below the prior audit's
provisional0.5ms P4 prioritization threshold; the timer exceeds it. This is a
prioritization observation, not a product/release acceptance threshold or proof
that a treatment will improve the suite. P8 outliers inflate some means without
establishing high intrinsic CPU cost.

Charset initialization includes compiled registration/hashes, prepared-map
attachment or fallback, and index-file handling. This interval is not the old
already-adopted lexer-map producer. Its exclusive subcosts and the later selected
collation setup remain unmeasured. Saving this entire interval is not assumed.

## Observer control and whole workload

| Parallel | Mode | Fork p50 ms | Fork p95 ms | Suite median ms | Suite maximum ms |
|---|---|---:|---:|---:|---:|
|4|off|25.621|32.165|611.621|621.860|
|4|on|28.690|37.396|599.423|621.715|
|8|off|34.867|50.997|479.958|806.607|
|8|on|37.026|53.462|571.971|583.864|

This is observation-only, so an ON suite faster than OFF is not a product gain.
P8 primary sample-loading tails include440.039ms (ON repeat2) and476.282ms (OFF
repeat2); OFF repeat2 suite806.607ms is retained. A warmup OFF sample438.443ms is
also retained and excluded only by the predeclared warmup rule. Fork itself did
not have a100ms tail. These observations do not reopen the separate tail issue
or establish that a tail disappeared.

Paired process Fork-p50 ON minus OFF (repeats0/1/2):

- P4: +2.902, +3.981, +2.043ms.
- P8: +0.851, +3.093, +9.313ms.

Common host-region totals closely track the existing guest common markers;
per-child differences are retained as `host_minus_guest`. No fixed observer
cost is subtracted. All new marks append to in-memory per-instance traces; no
file write or output occurs within these measured blocks. Existing startup
traces still flush after startup, as in the preceding measurement.

## Binding, correctness and limits

The exact guest's optimized functions inline the C candidates into
`Fn5573:init_embedded_server`. A plain function-name wrapper would not isolate
them. `acquire-map.py` downloads fixed artifact13628982950 from
[run42509593737](https://github.com/masahitojp/mariamem/actions/runs/42509593737),
uses checksum-pinned Binaryen133 and reproduces the adopted guest bytes and
symbol-map hash. `function-map-proof.json` retains all identities.

The overlay binds full canonical file/function hashes and unique control-flow
label+instruction anchors. It adds marks at the timer, locale, lexer lengths,
native-function hashes and JSON hash boundaries. Timer control-flow continuation
is not a contiguous physical source range. Charset uses the exact
`Fn961:init_available_charsets` entry/return. `bindings.json` keeps the anchors.
Removing the inserted marks reproduces the original instruction body byte for
byte before gofmt; no original operation, branch or return is changed.
The nil-checked per-module callback is installed only for ON and cleared at
common completion, before plugin workers start. No global child-ID map is used.

Generated-Go instruction files are **overlaid for observation**. Canonical
tracked generated code, guest patches, SQL, startup settings, public APIs and
release files are unchanged. Therefore `product_changes=false` in completion
means no committed product change; it does not claim the diagnostic binary has
pristine product bytes. One diagnostic binary serves OFF and ON; its hash and
all before/after overlay hashes are in inputs.json.

All16 processes passed SQL assertions, exact50/20 case counts,21 Forks/samples,
zero active mappings and empty owned scratch after cleanup. Eight concurrent
trace-reader contexts, their timer metadata and invalid-reader handling passed
focused unit checks. Analysis rejects a missing timer endpoint, duplicate mark,
missing timer metadata and charset overlap. No broad release/native parity,
Windows/Linux, race campaign or optimization acceptance is claimed.

## Reproduction and retained evidence

Read-only replay, with no removed source/build path required:

```sh
python3 benchmarks/shopforkstages/common-results/analyze-common.py --check
```

For a separately authorized rerun, prepare this measured harness commit in a
workspace with8GiB budget/12GiB free reserve. Run `acquire-map.py`, then `build.py`
and `run.py` under the experiment-workspace guard (1500seconds for build+run,
150seconds per process). The fixed plan allows one diagnostic build and16
processes. Use the report's analysis scripts for the derived remainder split.
The recorded tooling/active-work ceilings are30minutes/2hours; no CI is needed.

One deterministic gzip keeps all16 original observations, including warmups,
root records, child timestamps and timer metadata. Source-bound manifests,
analysis, focused checks and checksums accompany it. Individual raw trace/log
hashes are retained, not dozens of duplicate raw files or full generated code.
The symbol map, compiler, WASM downloads, binary and caches are reproducible
scratch and are removed after pushing the report. Workspace cleanup is checked
separately; no unrelated collaboration-root files are changed.
