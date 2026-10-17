# Ubuntu released-product performance

Human authorized native Ubuntu performance measurement after v0.5.2. This is a
finite evidence campaign, not runtime development, Qualification or publication.
No result is claimed before the CI artifact is reviewed.

Compare released **v0.5.0 / v0.5.1 / v0.5.2**, using the typed release pins in
`release/baselines/` and the canonical Git identity / Go binary-stamp checks.
Build unmodified `mariamem-host` and `ownedprepared` in independent, clean clones;
verify all six binary identities before measurement and again at completion.
The existing Go/Python observers must be identical except the known unused
retired export option; no guest, generated code or SQL oracle is changed.

Environment: native Ubuntu24.04 x86_64 GitHub-hosted runner, Go1.26.8,
CGO_ENABLED=0, Python3.14.8, prior pinned Python dependency inventory. Record
actual toolchains, dependencies, source/guest/provenance/binary hashes, CPU,
memory, kernel, cgroup limits and command receipts. An arm64 Docker VM is not
this platform. Do not compare raw Ubuntu timings to macOS as an engine ranking.

## Fixed cases and exit conditions

- **Matrix:** Go/Python, Fresh/Fork, Light, 10 MiB / 8 tables serial and 4 parallel;
  4 tests per suite, 3 trials of each of three versions: 108 measured cells.
- **Large reuse:** Go/Python 100 MiB / 8 tables **Fork only**, 4 tests per suite,
  3 trials per version: 18 cells. No 100 MiB Fresh or new profiling campaign.
- **Pilots:** Light with one test for each version/language/mode: 12 cells,
  excluded from reported performance medians.
- **Prepare once, reuse:** existing Python sharedhost small/medium (2 children)
  and 100 MiB (16 children). Pair v0.5.0→v0.5.2 and v0.5.1→v0.5.2 independently,
  with 6 ordinary pairs and 3 separate RSS-observed pairs per scale: 108 cells.
  Do not pool current-version observations from the two different pair windows.

Total **246 executions**, of which 12 are excluded pilots. One campaign runs at
a time. Matrix version order rotates/reverses; reuse retains its alternating
baseline/candidate order. Keep all slow values; report medians and ranges from
exact cohorts and distinguish v0.5.0 net product changes from the v0.5.1→v0.5.2
ownership comparison. No Testcontainers run is included.

Report whole workflow, Snapshot, child startup/use/Close, CPU, Go cumulative
allocation, Go RSS high-water and memory-mapping balance. Existing Go measurements
include their 25ms heap observer; product wall excludes the existing diagnostic
probes, which does not make observer overhead zero. Python matrix resource
samples are after SQL, not peaks. Reuse ordinary latency and sampled RSS are
separate runs. Linux PSS is not macOS physical footprint. No cross-language
performance ranking, no leak-freedom or tail-probability guarantee from finite
trials. A performance regression is retained for Human Review, not silently
rerun away or treated as a functional failure.

Stop on original SQL/transaction/isolation/cleanup oracle failure, identity or
observer mismatch, timeout, mapping leak, disk budget breach, or Go process
RSS >6 GiB at cell completion. RSS is an observed limit, not a hard RAM quota.
Campaign budget including builds is 7200 seconds, per-cell 900 seconds,
sharedhost pair campaign 1800 seconds, workspace 20 GiB, free reserve 8 GiB.
Budget exhaustion or partial cells mean incomplete, never PASS. Workflow has
150 minutes including setup, evidence upload and cleanup. No automatic runtime
fixes, scope reduction or extra repeats.

Run `python benchmarks/ubuntu-product/run.py --workspace WORKSPACE` in the pinned
native environment. `WORKSPACE/temp` must not exist. Output is compact JSON and
text under `WORKSPACE/evidence`; build/cache/source clones go under disposable
`temp`. CI removes owned temp even on failure and uploads evidence with the
exact harness SHA. After submission Codex hands off the run URL and stops;
the Human returns results for review.
