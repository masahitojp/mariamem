# Timer and charset startup audit, 2026-11-10

**Both are concrete optimization targets, but neither whole initializer can be
removed safely.** Start with the timer's millisecond-resolution probe, preserving
clock availability and frequency metadata. For charsets, first split registration
from deep collation setup; pre-reserving the registration hash is the smallest
candidate. Full sharing of initialized mutable charset objects is not recommended.
This is a source audit, not an implemented optimization or new speed measurement.

The material caveat is that timer metadata is used by SQL `ANALYZE`, even with
Performance Schema disabled. The current generated code also exposes a possible
compile-time/runtime clock-selection mismatch. Check the baseline SQL behavior
before accepting any timer treatment; do not hide a correctness change inside a
performance patch.

## Evidence boundary

- Product source_commit: `b1218737ffa0bc1d08e9b1285b9bcf6ccf8adc50`.
- MariaDB source_commit: `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`.
- Full source archive SHA256: `36319b89c4373cf35e5c5c08686625eccae2816257b6982a4815ff552b945845`.
- Existing [measurement](https://github.com/masahitojp/mariamem/blob/ad249307c1866d75629d976da181fb4c96b19748/benchmarks/shopforkstages/common-results/README.md)
  and retained observations are unchanged. Single M1/16GiB Mac, Go Pipe,
  16MiB/read1, shop70, three primary pairs each at P4/P8, 63 children per cell.
- The full pinned repository archive was inspected, including tests and PFS.
  No external submodules/plugins were acquired. Current portability patch disables
  PFS and dynamic plugins. Text search is not a complete pointer-alias proof.

| Existing observed region, child elapsed p50 | P4 ms | P8 ms | What this audit establishes |
|---|---:|---:|---|
| Timer characterization | 0.936 | 0.959 | Active resolution/overhead probes; frequency metadata has SQL consumers |
| Charset registry initialization | 2.059 | 2.143 | Built-in catalog, names, hashes, state-map attachment and XML-index handling |
| After registry until common initialization ends | 2.470 | 2.544 | Can include lazy collation setup and other option/path work; not exclusively UCA |

These are enclosing elapsed intervals with observation overhead and scheduling,
not exclusive CPU costs, additive medians or promised savings. No new benchmark,
guest build, CI, runtime patch, product decision or default change occurred.

## Timer: characterize less, retain timekeeping

Pinned source references below are relative to the MariaDB commit above.

1. `mysys/my_rdtsc.c:363–455` discovers clocks and initializes frequencies.
   The previously observed children all have unavailable cycles (four zero fields),
   nanoseconds frequency 1e9, microseconds 1e6, milliseconds 1000 and ticks 100.
2. `:519–541` probes resolution. `:290–330` repeatedly reads clocks until it
   sees jumps; milliseconds needs one jump, bounded by ten million iterations.
   This busy probe is a plausible source of the roughly 1ms interval. Its exact
   share is not measured, and timer p95 was 4.71/4.54ms, including scheduling.
3. `:545–630` frequency-calibration loops require cycles and are skipped for the
   observed profile. Optimizing those loops would not address this measurement.
4. The complete symbol census finds production metadata consumers in
   `sql/sql_analyze_stmt.h:42–48,66–74,115–118`, plus PFS normalization/display.
   SQL execution trackers divide elapsed ticks by the selected frequency.
   Disabling PFS does **not** justify skipping `my_timer_init` wholesale.

The smallest proposed treatment is to bypass only the millisecond resolution
probe in the exact WASI/no-PFS/no-cycles profile. Preserve clock availability,
frequencies, actual clock reads, timeouts and all native/fallback behavior.
The resolution field must have an explicit bounded-profile policy rather than
silently being advertised as calibrated. Do not bypass a resolution probe when
another enabled frequency-calibration path depends on its result. Broader
overhead/resolution removal is a separate extension if the small treatment helps.

### Baseline correctness question discovered during the audit

`include/my_rdtsc.h:153–157` can select `__builtin_readcyclecounter` at compile
time (routine29). The runtime initializer can then clear the unavailable cycles
fields to zero. In contrast, `sql/sql_analyze_stmt.h` selects its clock with a
compile-time `#if MY_TIMER_ROUTINE_CYCLES`, not the runtime availability result.

Current generated `Fn5573` sets routine29 and immediately clears both 16-byte
halves of the cycle metadata (`p0_pure.go:65197–65203`). The literal-address
census finds 13 references outside this initializer, all loading cycle frequency
at26639696. For example `p5_pure.go:1107414–1107415` divides tracked time by it.
This agrees with the measured zero cycle frequency, but **does not reproduce a
user-visible SQL failure** or prove these paths are exercised by the shop suite.
No old guest function map was used to assign new function names.

Before the timer prototype, run one bounded baseline `ANALYZE FORMAT=JSON`
query with actual table work and a short known delay, checking finite, plausible
execution timing and the subsequent SELECT. The upstream embedded test
`mysql-test/main/analyze_format_json_emb.test:10` already exercises ANALYZE with
SLEEP and table rows. If timing is broken, record it separately and decide a
WASI clock-selection correction; do not claim removing calibration fixes it.

## Charset: two different kinds of construction

```text
First charset lookup in each new guest
  init_available_charsets                 [observed ~2.1ms]
    initialize two name hashes
    register compiled definitions
    construct UCA1400 / 0900 names and descriptors
    attach lexer maps; handle Index.xml
  get_internal_charset
    if not READY: initialize selected charset/collation
      parse tailoring rules
      copy weight-page lengths and pointers
      prepare modified pages, contractions and their hash
      attach prepared booster where eligible
    mark this guest's descriptor READY
  remaining embedded options/path work   [combined subsequent ~2.5ms]
```

- `mysys/charset.c:593–650,704–742` registers descriptor pointers and builds
  charset/collation name hashes. `strings/ctype-uca1400.c:273–361` constructs
  names, allocates descriptor/name/comment storage and registers UCA variants.
  Its loops visit 5 encodings ×26 tailoring slots ×2 pad ×2 accent ×2 case =1040
  combinations; skipped IDs/unavailable encodings mean this is **not** an
  observed registration count. `strings/ctype.c:1439` performs the packed
  allocation and string copies. UCA0900 aliases add further descriptors.
- Both hashes start at64 elements, growing by16. `mysys/hash.c:80–108` passes
  these sizes to the dynamic array; `mysys/array.c:162–197` reallocates on growth.
  Pre-reserving collation-hash capacity can avoid repeated allocation requests.
  It does not remove key hashing/insertion and realloc need not copy every time.
  Measure actual records, growth count and allocation cost before choosing a size;
  do not overallocate the much smaller distinct-charset hash just for symmetry.
- `mysys/charset.c:862–924` performs lazy initialization under a mutex and sets
  `MY_CS_READY`. `strings/ctype-uca.c:34460–34575` builds weight levels and
  contractions. `:34698–34716` reuses initialized UCA data for an encoding and
  tailoring **inside one guest**, not across Forks. This belongs after registry
  initialization when first selected; its exclusive cost remains unknown.
- The adopted `guest/source.patch` shortcut precomputes the booster for exact
  UCA1400 default PAD ai_ci IDs2048/2304 and levels0–2. It does not precompute
  the whole registry, names, weight-page pointer arrays or contractions. Existing
  prepared lexer maps likewise do not remove registry construction.

Immutable names/descriptors/templates are a plausible later preparation target.
Live `CHARSET_INFO`, READY flags, handler pointers, use statistics, lazy UCA
state, locks and allocation ownership are mutable. Sharing those objects directly
would create a substantially different correctness problem. Do not remove other
collations or change defaults to make the benchmark faster.

## Bounded next work, in priority order

1. **Timer**: baseline ANALYZE correctness check, then one resolution-only
   prototype with an exclusive marker around that probe. Preserve all frequencies
   and test ordinary timekeeping and SQL timing. The present target is part of
   ~1ms/Fork, not the whole timer interval guaranteed removable.
2. **Registry**: count actual definitions/hash growth, mark registration separately
   from selected-collation initialization, then try only hash preallocation if
   repeated growth is material. Keep dynamic overflow and XML fallback. Compare
   exact catalog IDs/names/aliases and lookup results, not just row counts.
3. **Selected collation**: only if its measured cost warrants it, partition
   tailoring parsing, weight setup and contractions. Reuse immutable prepared
   data with native comparison of equality, ORDER BY, UNIQUE, accents/case,
   PAD/NOPAD and non-default fallback. This is not yet an implementation proposal.

Each treatment stays separate. First require unchanged results/cleanup, then
compare uninstrumented Fork and complete shop70 time at P4/P8 with alternating
arms and retained tails. Do not convert several measured regions into a claimed
sum of future savings. Host/platform acceptance remains later, separate work.

## Reproduction and retention

In an isolated worktree containing this report's scripts, the plan permits source
acquisition and inspection only (90min active,15min tooling,0 runtime/CI,4GiB
owned/8GiB free). `acquire.py` checks the exact Git commit through the GitHub API
and the release lock's archive SHA256 before extraction. It requires an empty
owned `../temp/upstream` destination. Then:

```sh
python3 benchmarks/timercharset/acquire.py
python3 benchmarks/timercharset/audit.py ../temp/upstream/server-83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e --check
```

The audit checks canonical generated/patch bytes against the product commit,
replays the full symbol census and literal-address scan, and compares retained
results without modifying them. Literal-address scanning is deliberately not
presented as indirect-use proof. `results/source-audit.json` retains selected
source hashes and generated consumer anchors; `SHA256SUMS.json` binds the compact
report, scripts and evidence. Full upstream/generated copies and downloads are
disposable. Original runtime observations remain in their prior report, not
duplicated or relabeled here. Main and the unrelated active checkout are unchanged.
