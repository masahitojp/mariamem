# Prepared UCA canonical candidate — local checkpoint, CI pending

This checkpoint implements the already-authorized candidate preparation.
**The next requirement is exact-source independent builds/regeneration and the
Mac/Ubuntu runtime matrix; adoption and main integration remain open.**
The original single-Mac spike is not promoted into platform or release evidence.

## Identities and production delta

- Main base retained through `47121e1b` (PR113 documentation/version preparation).
  No version is chosen by this optimization task.
- Actual C guest bootstrap: `275c1807f8d7dabfdd1aa529ff598f68d319820b`.
- Observed WASM: `6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe`.
- Mac runtime controls: `c7472177239f7b9c14f425034940ef9c2b73bf19`.
- Paired measurement candidate: `40dd1e2ae57f85a137a8cf66d29f8cc6231899c4`;
  it includes current main. Its Go runtime tree is unchanged from c7472177.
- Preserved baseline: `676515eb9244fc501b5a600791b0cf0a6174fecd`, guest `96129c…`.

`guest/source.patch` owns the small constructor/const-pointer delta. The
maintained three-level JSON numeric input is expanded into a typed C header
only during preparation, after checking the pristine MariaDB/archive/Unicode
identities. Provenance pins the five input files and emitted header, and the
canonical build guard checks that attestation. The guest has no JSON/gzip decoder.

The selector still requires exact default builtin IDs2048/2304, level0–2 and
the expected shared level identity. Every other selector uses the original
producer; optimized comparison consumers are unchanged. The private verification
switch is supplied through a package-local test seam. Ordinary profiling and
ambient host variables cannot enable table reconstruction/verification.

The generated Go/pins are authored from the observed output with the normal
installer. No experimental manifest bypass or generic ABI normalizer ships.
All nineteen ownership bodies and their call relationships were compared:
only the explicitly mapped function relocation, same-address-role BSS shift of
2,754,112 bytes and one identical read-only string are permitted. The505 TLS
bytes and G0–G3 values match. Exact runtime guards still accept one guest and
full pinned bodies; changed address/callee/instruction controls reject mutations.

Initial data grows from6,856,219 to9,610,331 bytes. This trade removes repeated
booster construction while keeping the original fast readers. Guest/tool/input
pins, actual symbol attribution and the wheel's license inventory are updated;
old receipts remain under their original identities. One bootstrap build is
explicitly UNQUALIFIED, with no new independent-build or platform PASS claim.

## Local verification

On macOS27.2 arm64: actual guest six-table full memcmp; one-cell corruption
rejection; normal/profiling separation; actual worker trap with healthy peer;
complete mapping disposal; native MariaDB12.3.3 differential SQL; two independent
children retaining their baseline; Snapshot transaction/three-child smoke; and
all six heap/mmap unsafe/protected/race ownership controls PASS.
The native comparison includes ordering, grouping, pairwise equality/comparison,
weight strings, UNIQUE errno, NULL/empty/NUL/Unicode and Czech contraction cases.
It does not establish arbitrary collation/application support.

Focused input/inventory/binding/license tests passed. The packaging mirror test
caught the changed license inventory; synchronizing the mirror and rerunning
that owner closed it. The corrupt-memory test initially scanned the reserved
rather than committed range and was fixed before its PASS. No product memory
access policy was relaxed. Go auto-stamping initially selected the outer nested
worktree; the attribution host was rebuilt in an own-`.git` clean clone and its
embedded source/clean flag checked. Earlier failed attempts are retained locally.

## One bounded current-main comparison

Single Mac, Go1.26.10, CGO1, Python3.14.10/PyMySQL1.2.3, GOMAXPROCS8.
Five alternating fresh-process pairs, one separate warmup per label, four
**sequential retained** children per process, explicit cap4,20 warmed SQL repeats.
Per-process child medians are reduced to the median of five processes; all five
pairs are retained. Times below are milliseconds except the named RSS rows.

| Metric | Baseline | Candidate | Change |
|---|---:|---:|---:|
| Fork elapsed | 35.966 | 27.535 | -23.4% |
| Fork host CPU | 48.577 | 41.051 | -15.5% |
| Whole four-child fixture | 596.735 | 565.264 | -5.3% |
| ASCII comparison query | 1.535 | 1.566 | +2.0% |
| Mixed comparison query | 0.987 | 0.994 | +0.7% |
| One held child RSS increment (MiB) | 78.953 | 75.031 | -5.0% |
| Four held children RSS increment (MiB) | 310.391 | 297.172 | -4.3% |

Fork elapsed/CPU and whole-fixture wall improve in every paired process.
ASCII median is +2.0% (four pairs slower, one essentially unchanged); mixed is
+0.7%. This is a small cohort, not proof of SQL performance equivalence, a
regression threshold decision or parallel scaling. Carry that small SQL movement
into adoption review rather than silently declaring it unchanged. No outlier was
removed and no comparison to the old spike's absolute times is made.

The compact [inputs](uca-prepared-candidate-evidence/performance-inputs.json),
[per-process reductions](uca-prepared-candidate-evidence/performance-summary.json),
[assessment](uca-prepared-candidate-evidence/assessment.json) and
[checksums](uca-prepared-candidate-evidence/SHA256SUMS.json) are the proposed repo
set. Full per-child observations, warmups, failed attempts and the read-only
reducer remain compact local evidence; build/temp/cache state is disposable.
The unchanged probe is pinned to the original experimental commit in inputs.
Its fixed prior native performance-result constants remain historical; the new
native differential correctness run is recorded separately. These are not a
fresh native performance benchmark.

To repeat, build both named sources with Go1.26.10/CGO1/-trimpath in clean clones,
check `go version -m` and `--snapshot-info`, use the pinned probe with
`--mode measure --host PATH`, clear MARIAMEM_/MYSQLMEM_ ambient variables,
set GOMAXPROCS8, alternate five fresh-process pairs after separate warmups, and
retain CPU/wall/query/RSS/cleanup results together. SDK version and both exact
source/guest/binary hashes belong with each new cohort; do not relabel this one.

## Remaining finite gate

The new `uca-canonical.yml` source build makes two independent guests and checks
the expected bytes. Native macOS15 arm64 and Ubuntu24.04 x86_64 independently
regenerate Go, run the canonical build guard, actual table/corruption/profiling
and worker tests, native SQL/two-child/cleanup and existing Snapshot smoke.
Their original artifacts must be saved/reviewed before claiming this matrix PASS.
Those rows are PENDING, not inherited from PR112's earlier source-only CI.

No InnoDB setting, prewarming/cloning, resource campaign, public API, supported
wire/profile expansion, main adoption, Qualification or release is included.
