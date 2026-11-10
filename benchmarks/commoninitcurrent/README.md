# Remaining common initialization: source audit, 2026-11-10

There are still repeated computations worth measuring, but this audit does not
establish which one dominates or how many milliseconds can be removed. The next
step should be one bounded subdivision of the existing common interval, not a
new registry architecture or blanket initialization bypass. Prefer prepared
immutable metadata if it proves material; preserve per-DB mutable state.

Product source_commit: `b1218737ffa0bc1d08e9b1285b9bcf6ccf8adc50`.
MariaDB source_commit: `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e` (12.3.3).
This is a source-only investigation: no new runtime measurement, guest build,
product patch, CI, adoption, or release. `plan.json` fixes the scope and budget.
The 19 selected upstream files were obtained by exact commit, with Git blob and
SHA256 verification; `source-files.json` records their identities and URLs.

## Measurement boundary and what is already optimized

The preceding shop70 Pipe experiment is bound to result commit
[`7ebc279e`](https://github.com/masahitojp/mariamem/tree/7ebc279e4c8ed2a25dbf7e54f9c93e14238f8b2c/benchmarks/shopforkstages/results).
Its pooled per-child medians, in milliseconds:

| Interval | P4 | P8 |
| --- | ---: | ---: |
| Uninstrumented whole Fork | 26.398 | 32.102 |
| Instrumented whole Fork | 29.375 | 42.392 |
| Instrumented common initialization | 7.652 | 10.233 |
| Instrumented InnoDB plugin | 6.060 | 5.965 |

The stage numbers are nested, from instrumented runs; they are not additive
parts of the uninstrumented Fork. P8 has substantial observer perturbation.
There are no individual costs for the candidates below in that evidence.

`common` means `embedded_begin` to `embedded_options_complete`, as defined in
[`scripts/guest_init_hooks.py`](https://github.com/masahitojp/mariamem/blob/b1218737ffa0bc1d08e9b1285b9bcf6ccf8adc50/scripts/guest_init_hooks.py#L6).
It is wider than `init_common_variables()` and ends before
`init_server_components()`:

```text
init_embedded_server
  thread / early variables / logger
  load_defaults
  sys_var_init + handle_early_options
  my_timer_init
  init_common_variables
    thread environment / per-DB state
    locale string lengths
    status registration / option parsing / paths / limits
    error messages / lex_init / SQL-function hashes / JSON keyword hash
    charset selection / filesystem capability check / other initialization
  tmpdir / SSL / umask
init_server_components                 ← outside this interval
  MyISAM / plugins including InnoDB / remaining components
```

Call boundaries: `libmysqld/lib_sql.cc:532–613`, `sql/mysqld.cc:4097–4670`.
`init_libstrings()` is effectively empty for EMBEDDED_LIBRARY (`mysqld.cc:3615`);
its name is not evidence of expensive string initialization.

The current canonical `guest/source.patch` already supplies prepared UCA boosters
and compiled charset lexer state/identifier maps. Issue126's state-map producer
is therefore **not a new candidate**. The host's process-static image contains
initial module data, not the runtime-populated heaps/hashes below. Reusing that
image does not itself eliminate these initialization calls. This is not a plan
to clone an initialized server or share its locks/allocator across children.

## Three candidates

### A. Repeated timer characterization: measure first, do not bypass yet

`lib_sql.cc:589` calls `my_timer_init(&sys_timer_info)` on the embedded startup
path. `mysys/my_rdtsc.c:363–630` detects available clocks, samples their overhead,
and measures resolution. The resolution helper (`:290–330`) repeatedly reads a
clock until it observes changes; its loop bound is ten million iterations. For
milliseconds it stops at the first change, not after three milliseconds.
Additional frequency-calibration loops are conditional on available timers.
Neither the loop upper bound nor the native-host behavior is an observed guest
cost. `include/my_rdtsc.h:153–245` has compiler/architecture-dependent branches;
the exact compiled WASM backend and actual enabled routines remain to be checked.

Potential reduction: avoid repeated empirical characterization if the guest's
clock contract supplies the needed facts, or reuse only valid process-level
characteristics. This is runtime/host-dependent metadata, not a table to blindly
precompute on the build machine. Preserve availability, units, resolution,
error behavior and every consumer's requirements; overhead measurements may
change with load and cannot simply be declared invariant.

One known consumer is Performance Schema normalization
(`storage/perfschema/pfs_timer.cc:67–87`). The WASIX portability recipe sets
`PLUGIN_PERFSCHEMA=NO`, but the selected-file audit is **not a complete consumer
census**. It does not prove `sys_timer_info` is dead or authorize removal.
Next evidence: exact-build caller/consumer/backend check plus one aggregate
start/end duration; no per-clock-call logging. This is the first diagnostic
priority because calibration has time-dependent loops, not because a large
saving has been measured.

### B. Fixed SQL-function and JSON-schema lookup construction

`item_create_init()` (`sql/item_create.cc:6795–6823`) constructs two hashes:
normal SQL functions and Oracle-mode functions. Both insert the common and
geometry registry entries; the latter then applies Oracle overrides. Each
append loops through `my_hash_insert` (`:6688–6740`). `find()` (`:6775–6792`)
first consults the hash, then falls back to a function plugin. Cleanup frees
both hashes (`:6826`). Thus merely disabling Oracle startup work would change
later SQL-mode behavior and is not the proposal.

`setup_json_schema_keyword_hash()` (`sql/json_schema.cc:3039–3055`) inserts
**75 fixed entries** into a hash initially sized for **1024 entries**. Its
consumers at `:2824` and `:2885` select factories; factories still allocate
per-statement objects in the THD memory root. The translation-unit-local hash
has startup insertions and shutdown cleanup; no other mutations were found in
that file. Some consumers compare pointers to exact array entries, so a prepared
lookup must return the original entry identity, not copies.

Potential reduction: generate a build-bound lookup index for immutable built-ins,
resolving indices to each guest's local entries. Keep Oracle overrides, exact
name/collation semantics, unknown-name/plugin fallback, conditional-build sets,
and all per-statement allocation. Do not share heap pointers or a mutable HASH.
JSON hash capacity reduction is a smaller alternative to check before replacing
lookup machinery; fewer reserved slots alone do not prove faster startup.

The native-function class exposes append/remove/replace; this audit has not
exhausted all external callers. A native-function replacement needs that census
and full lookup-equivalence checks first. JSON's local ownership makes it the
smaller correctness surface, but **neither lookup has a measured exclusive cost**.

### C. Locale and lexer literal lengths: smallest semantic change

`init_locale()` (`sql/sql_locale.cc:4804–4815`) visits **138 locales × 5 tables =
690 table visits**, including shared TYPELIBs. `update_lengths_in_typelib()`
(`:4792–4801`) allocates a length vector if absent, but recomputes `strlen` for
every entry even when the vector already exists. This also revisits tables shared
by locales or the formatting/month-name fields. These are source-derived counts,
not 690 unique tables or observed allocations.

Separately, `lex_init()` (`sql/sql_lex.cc:688–701`) fills literal token/function
name lengths with `strlen` on every startup. This is different from the already
prepared charset state maps. The lexer hash itself comes from generated
`lex_hash.h`; do not describe it as entirely rebuilt here.

Potential reduction: generate exact byte-length vectors for fixed locale tables
and initialize literal token lengths at build time. Preserve UTF-8 **byte** lengths,
all locales, token inventory, array terminators and field-width bounds. Keep
TYPELIB and other mutable state guest-local, and preserve ownership at shutdown:
the existing vectors use `my_once_alloc`, so prepared storage must never be freed
as owned heap. Dynamic/unrecognized inputs, if supported at that boundary, retain
the original path. Limiting locale support to en_US is not an acceptable shortcut.

This is the simplest semantic candidate, but small loops may be a small fraction
of 7–10ms. Source structure alone does not justify a guest rebuild or a speed claim.

## Work deliberately not proposed

- Charset-name/collation-name hashes (`mysys/charset.c:593–650,704–751`) remain
  mutable: registration updates CHARSET_INFO flags/pointers, dynamic extra entries
  exist, lazy initialization and statistics remain instance-local. The previous
  lexer optimization does not make the entire registry immutable.
- System-variable registration (`sql/set_var.cc:62–113,607–653`) supports
  additions/removals and versioning; `SET`, option parsing and plugin behavior
  must remain intact. `get_options()` builds a descriptor array then performs
  validation/side effects (`mysqld.cc:9237`); caching the final parsed settings
  would incorrectly reuse per-DB values and paths.
- Thread locks, startup times, temp paths, timezone, FD limits, filesystem
  case-sensitivity checks, mutable status counters and error handling are not
  discarded as "common overhead". `add_status_vars()` already skips sorting and
  locking during early startup (`sql/sql_show.cc:3650–3700`).
- MyISAM's key cache, InnoDB and Aria are outside the common interval. Their
  earlier timings must not be used as exclusive costs for these candidates.

## Recommended next bounded step

Add aggregate in-memory timing buckets for A, locale/lex lengths, B, and the
remaining common work. Flush once after startup; avoid logging inside loops.
Count charset initialization separately if nested under another bucket so that
nested durations are not added twice. Retain source, guest and binary identity.
First verify sums against the existing common span, then use the existing shop70
P4/P8 workload with paired observer-off/on runs. Report per-child p50/p95,
>100ms counts, observer delta and whole-suite time; preserve all slow children.

A suggested bound for a separately authorized follow-up is one instrumented
candidate build, three off/on pairs per P4/P8, at most two hours active work and
30 minutes tooling. If the build cannot fit, report that blocker before expanding
it. This audit starts none of those runs. Before implementation, choose only the
measured material bucket; a provisional prioritization threshold is >=0.5ms P4
median with observer uncertainty smaller than the effect. Below that, stop this
line rather than redesigning all registries. This threshold is a proposal, not
an adopted product/release gate. Any prototype must also improve uninstrumented
whole-suite behavior and preserve SQL/cleanup correctness.

The strongest objection is that further instrumentation/build work could cost
more than these residual loops save. Existing evidence cannot resolve this.
The fixed one-build/bucket exit limits that risk, and permits a no-change result.

## Reproduction and retention

Prepare a disposable workspace using this experiment branch. From its worktree:

```sh
python3 benchmarks/commoninitcurrent/acquire.py
python3 benchmarks/commoninitcurrent/audit.py
```

`acquire.py` verifies the product commit and upstream commit, fetches only pinned
files and checks each Git blob; downloads live in the owned sibling `temp/`.
`audit.py` verifies SHA256 and prints deterministic source counts read-only.
Compare its stdout with `source-facts.json`. `source-files.json`,
`product-inputs.json`, this report and `SHA256SUMS.json` survive cleanup; the
upstream checkout, caches and build outputs are not committed. No new runtime
results exist to retain. The earlier workspace setup failed due to a wrong script
path before source acquisition; it was cleaned and the corrected recipe rerun.
Additional selected-file acquisition required network permission; it performed
no builds or runtime execution. Unrelated collaboration-root changes were left
untouched. No runtime tests are warranted for this report/acquisition-only diff.
