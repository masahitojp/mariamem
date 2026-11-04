# Issue106: remove UTF8 UCA booster construction and consumers

Fork became cheaper, but the tested ASCII string SQL became sufficiently slower
that the whole fixture took longer. **Recommendation: do not adopt this switch
as the default.** The result confirms a useful startup-cost hypothesis; it does
not establish an overall application improvement. Preserving comparison speed
while avoiding repeated booster construction is a possible separate experiment.
Issue103's initialized-state reuse proposal remains separate.

| Median metric | Baseline | Booster off | Change |
|---|---:|---:|---:|
| Fork elapsed, one child | 36.47ms | 27.77ms | −23.8% |
| Fork host process CPU | 49.43ms | 41.52ms | −16.0% |
| RSS increment with one retained child | 78.45MiB | 72.39MiB | −6.06MiB |
| RSS increment with four retained children | 309.66MiB | 285.88MiB | −23.78MiB |
| ASCII query elapsed, 1000 rows | 1.59ms | 3.58ms | 2.25× |
| Mixed-string query elapsed, 1000 rows | 1.04ms | 1.09ms | +4.8% |
| Whole process, setup → cleanup | 571.75ms | 708.77ms | +24.0% |

Each child metric first takes the median of four children in one process, then
the median of five processes. RSS uses host RSS minus that process's zero-child
reading; it is not PSS, an exclusive allocator measurement, or peak RSS.
The five paired Fork changes were −32.8%, −18.1%, −23.2%, −28.0%, −22.8%.
All five pairs improved; no trial/tail was removed. This is a small local sample,
not a confidence interval or a cross-platform performance guarantee.

The full-time result is not contradictory: the median process sum of four Forks
fell 147.25→113.34ms, while its four SQL stages grew 247.50→422.28ms. These are
separately summarized components, not an additive decomposition of the median
whole process. This fixture repeats each query 20 times in each child; it is
intentionally SQL-heavy. A different query count or different SQL can change the
exchange. The ASCII fixture has long common prefixes. Mixed strings usually
mismatch the comparison literal early; +4.8% is not a bound for Unicode SQL.

## Result matrix and change

| Check | Result |
|---|---|
| Pinned guest build and generated native host | PASS, UNQUALIFIED development route |
| Native12.3.3 vs baseline/candidate collation vectors | PASS |
| Snapshot child replay, isolation, UNIQUE1062, cleanup | PASS |
| Wrong-seed negative controls on both binaries | PASS: expected failure, cleanup successful |
| Exact experimental worker-ABI binding and rejection controls | PASS |
| Alternating five-pair measurement + separate warmup | PASS |
| Read-only summary/checksum replay, three rejection mutations | PASS |
| Ubuntu, full release matrix, application-wide SQL qualification | SKIP, outside this spike |

`guest/experimental.patch` disables the booster producer and all four UTF8
consumer macro expansions together, only for `__wasi__`. The ordinary existing
comparison paths remain. Defaults, Unicode weights, charset selection and the
canonical `guest/source.patch` are unchanged. Native equality covers utf8mb3/
utf8mb4 UCA1400 ai_ci ordering, pairwise equality/less-than/STRCMP, weight strings,
GROUP BY, UNIQUE errors, NULL/empty/PAD/accents/case/NUL and selected contractions
(including explicit Czech collation probes). This finite corpus does not prove
all collations or SQL sequences. The speed difference is an A/B observation of
this paired code change, not an exclusive profiler attribution of every ms.

## Identity and method

- Product behavior base: `bc00b8e66e5fd57bc9b2127001faf8e05952b417`.
- Guest/build source origin: `2b4a209f0f9d8864fbcc56e16efff8c54c36cad0`.
- Host-stage source: `839516fb6df9873c8e1ab23fe7a38130cd0c9c3a`; only the
  experimental development installer differs from the guest origin. No product
  Go behavior change. Both commits were clean before building/measuring.
- Guest hashes: baseline `96129c76872ab0891329e8e356233d691208195654e878a2853139901712d05f`;
  candidate `9f5a35f1bbfecda0450bdf2e79c402d2e2abd301b8af74eb5a2398b68e35bbd2`.
- One macOS arm64 host; Go1.26.10, CGO off, GOMAXPROCS8; Python3.14.10,
  PyMySQL1.1.2. Five alternating fresh-process pairs, four **sequential** Forks
  retained per process, explicit cap4; this is not a parallel-four batch.
- Each process starts/seeds/captures a baseline, then forks and verifies four
  isolated children. Each child primes and repeats each fixed query20 times.
  SQL assertions and cleanup are mandatory. Warmups and earlier setup pilots
  are separate from the ten primary records.
- Host-only CPU/RSS comes from macOS libproc. CPU tick→ns conversion is checked
  against a process CPU clock. Controller work is excluded from host CPU;
  whole-process wall includes Python startup, seed, connections and cleanup.
- Native correctness reference: MariaDB12.3.3 arm64 image
  `sha256:23ccfa2f2df26837c8f397a8f9a070ad728768c095d246edd07cd8d24e9ec40c`.
  Native is not a performance comparator. See the provenance bundle for digest,
  compiler/builder/converter pins, file inventories and exact commands.

The original single-guest worker-allocation ABI guard correctly rejected the new
whole-guest hash. The experiment adds a development-only exception bound to one
manifest hash and this exact candidate guest/module. The three accepted worker
functions retain their exact package/name/normalized-body hashes; all6,856,219
initial data bytes and the initializer function are identical. Original
Module/yield/body checks still run. Unknown guest, inventory/data/body changes
and release-mode override are rejected. This experiment-specific installer is
not a proposal to broaden the product/release acceptance guard.

Cold LLVM acquisition was interrupted before C compilation, then resumed and
verified by full archive hash. The subsequent single guest build completed in
1516.84s; native generation/smoke completed in284.65s. One initial installer guard
failure and one DNS-restricted acquisition failure remain recorded as failures.
The Human extended this trial's guest watchdog40→60min, then authorized finishing
the comparison/evidence/cleanup beyond the initial work-time budget. These are
one-off authorizations, not permanent policy changes; disk budget18GiB and
minimum free16GiB remained in force. Build/acquisition timings are setup records,
not warm/cold setup-cost claims.

## Evidence, reproduction and retention

[Summary](results/summary.json), [ten primary records](results/measurements.json),
[inputs](results/inputs.json), [controls](results/checks.json.gz),
[checksums](results/SHA256SUMS.json), [native vectors](results/native-reference.json).
Full inventories are in `provenance.json.gz` (one source inventory plus explicit
`$base`/`remove`/`set` deltas and a `$ref` for its identical copy); build logs/events in
`build-events.json.gz`. Published metadata/log prefixes are normalized; original
and published hashes are retained in `publication-transforms.json`. Provenance
hash references identify original artifacts, not normalized copies. Raw
API/archive source differed only in control-character spelling in a comment;
the compiled C file was verified against the patched, hash-pinned archive member.

Read-only verification requires only Python's standard library and these files,
even after all build/temp output is deleted:

```sh
python3 benchmarks/ucaboosteroff/results/analyze.py \
  benchmarks/ucaboosteroff/results --check
```

A fresh A/B rebuild uses an experiment-workspace `temp/source` clone at the guest
origin above, the exact builder/source/toolchain pins and normalized command from
`provenance.json.gz`, and the committed experimental patch. Build the development
guest; then advance only the installer to the pinned host-stage commit. Set
`MARIAMEM_EXPERIMENT_THREAD_BINDING` to a byte-exact copy of
`results/experimental-binding.json` when running the development native pipeline.
The existing `dev_guest` source-origin rule verifies this host-only transition.
The retained harness expects `temp/{source,dev-guest,dev-native,baseline-host,venv}`
and sibling `evidence/` under a fresh disposable workspace. Copy probe/runner/
reducer and exact binding there; use Python3.14/PyMySQL1.1.2 and the pinned native
image to regenerate the reference. `run_compare.py --phase pilot` must pass
before `--phase measure`. Commands contain normalized output locations; expand
those to the new owned workspace, never reuse another trial's receipts.

Generated Go/WASM, LLVM/SDK/downloads, binaries, cloned source, venv and caches
are disposable. They are not part of this report. Candidate adoption, main
integration, qualification and release remain separate Human decisions.
