# Default UCA initialization: diagnostic subphases

2026-11-11. **The remaining default UCA work is mostly constructing rule/
contraction data and populating its hash, not allocation or zeroing alone.**
A bounded data-template prototype is worth considering; this observation does
not establish a safe reusable representation or any performance improvement.
The timer change is already adopted on main. No additional UCA product change
is included in this experiment.

## Observed scope and result

Exact clean runtime source_commit `500020e7dc6d702ef059f0e73a4bab738103b774`.
Apple M1 / 16 GiB / macOS 27.2, Go 1.26.10, Pipe, GOMAXPROCS=8, GOGC=100,
P4, cap=5, 16 MiB buffer pool and read_io_threads=1. One diagnostic Go-overlay
build; two shop70 processes without warmup. Each has 50 shared read cases,
20 private write cases, 21 Forks and one Fresh. All 140 SQL cases passed;
active mappings returned to zero and scratch directories were empty.
No guest rebuild, heavy CI, Ubuntu observation or product patch was performed.

For each Fork, sum the five observed default collation intervals, then compute
quantiles across 42 Forks. Values are inclusive **elapsed** time with observation
enabled, not exclusive CPU or an observer-off speed comparison.

| Phase | Fork p50 ms | Fork p95 ms | Share of aggregate UCA time |
| --- | ---: | ---: | ---: |
| Page lengths/pointers and tailored-page preparation | 0.484 | 0.928 | 22.1% |
| Contraction arrays/flags, rules and built-in contractions | 0.835 | 1.440 | 37.8% |
| Hash allocation | 0.070 | 0.127 | 3.3% |
| Hash zeroing | 0.232 | 0.320 | 10.2% |
| Hash population | 0.559 | 1.163 | 26.1% |
| Remaining work, including booster path and next-level validation | 0.003 | 0.005 | 0.1% |
| Setup | 0.003 | 0.005 | 0.1% |
| Total selected UCA initialization | **2.211** | **3.958** | 100% |

Medians are not additive. The residual outside nested phase intervals is below
0.3% of aggregate parent time. Individual collation observations, including all
tails, are retained in `observations.csv`; two Fresh samples are reported
separately in `summary.json` and are insufficient for a Fresh performance claim.

Each startup initializes IDs 2048/2304/2560/2816/3072, respectively
utf8mb3/utf8mb4/ucs2/utf16/utf32_uca1400_ai_ci. Each observed phase occurs three
times per collation (three comparison levels). The generated hash initialization
zeros 245,760 bytes per occurrence: 15 occurrences mean **3,686,400 bytes of
hash zeroing per startup**, not measured saved memory or an RSS reduction.

## Code attribution and limitations

The pinned MariaDB source is `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`.
`verified-source.json` contains all four file hashes and the Git blob identity
used to acquire exact bytes. `strings/ctype-uca.c` establishes:

- `my_uca_init_weight_level` prepares page arrays, initializes contraction data,
  applies rules/built-ins, allocates/zeros/populates the contraction hash, then
  considers boosters.
- The hash has 4096 cells; generated WASM layout uses 60 bytes per cell. Insertion
  uses probing on collision. The contraction list itself appends items; this is
  not evidence of a quadratic list search or problematic collision rate.
- `my_uca1400_info_tailored[encoding][tailoring]` reuses initialized levels within
  one guest. It does not avoid their reconstruction in each new DB guest.
- `mysys/charset.c` retains mutable ready state, statistics, handlers and locking;
  a reusable payload must not share those live descriptors between DBs.

`rebind-proof.json` compares complete generated function bodies (465, 468, 610)
with the prior observation, replacing SIMD helper names only by hashes of their
complete definitions. This closes helper renumbering, not a claim of new speed.
`overlay-proof.json` records current file hashes and exact instrumentation
anchors. Removing injected calls recovers the original function instructions.
No guest behavior or initialization is intentionally skipped.

The observer measures phases at generated-code boundaries and writes one compact
record after each selected collation's total interval. Logging may affect later
scheduling; timer/map callbacks add overhead. This sample selects a next target,
not an observer-off product benefit, production CPU share or a platform gate.
The earlier approximately 2.35 ms observation has different source/toolchain
context and must not be interpreted as a before/after improvement here.

## Recommendation and next bounded decision

Prefer investigating a prepared **data-only** representation of default
contractions and their hash, ahead of an allocation/zeroing-only optimization.
Those construction intervals represent 63.9% of aggregate observed UCA time.
This is an opportunity estimate, not saved time: copying, relocation, validation
and ownership cost will remain. The approximately 2.21 ms total also bounds the
local opportunity; this is not the whole Fork cost.

Before a prototype changes runtime behavior, enumerate the backing arrays and
all writes after initialization; determine which pointers require relocation.
Keep per-DB ready state, locks, descriptors, allocation ownership and fallback
private. Restrict the first candidate to the five default IDs/no tailoring;
unsupported layouts must use the original path. Fail the candidate if exact
payload equality, representative native SQL/collation behavior, child isolation
or completed cleanup cannot be preserved. No concurrent expansion into #103's
whole-runtime template is needed. A subsequent performance test must use
observer-off paired binaries and retain complete-suite tails. No additional
heavy CI is justified by this attribution step alone.

## Recompute and reproduce

`python3 benchmarks/uca-default-init/analyze.py --check` recomputes the summary
from retained CSV, read-only, with no deleted build/temp dependency. SHA256SUMS
covers the compact data, analysis, reproduction tooling and attribution records.
Routine console logs, upstream source copies, full REST responses and build
caches are not repository evidence.

To repeat observation in an authorized disposable workspace:

1. Fetch/resolve the runtime source above and harness
   `d24087eedd21c6384c231fb119c8e98da7b370aa`, plus prior observer
   `b0c457e1d314b8a957ff7b149d400be4ae05a146`, as commits using
   `scripts/git_identity.py`. Start a clean worktree at the runtime source.
2. Copy this directory's `probe.py`, `probe.go`, `rebind.py` and
   `rebind-proof.json` to sibling `evidence/`; create sibling empty `temp/`.
   Run `python3 ../evidence/rebind.py` from that clean worktree. It validates the
   full-body correspondence against fetched Git history.
3. Under `experiment_workspace.py` / `experiment_disk.py`, reserve 8 GiB budget
   and 8 GiB minimum free space; run Python 3.14 on `../evidence/probe.py` with
   1500 s timeout. It asserts the clean exact source, builds Go 1.26.10 into
   owned caches, uses the pinned harness and checks both runs' SQL/phase/cleanup
   oracles. Network/toolchain acquisition is needed if not cached. There is no
   automatic guest build or CI dispatch.
4. Reduce records into the same CSV columns (nanoseconds/counts), retain pins
   and checksums, then remove owned caches, binary, extracted harness and source
   copies. New measurements are new evidence; do not overwrite this receipt.
