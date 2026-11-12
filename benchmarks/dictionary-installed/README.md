# Installed dictionary candidate: fixed comparison

This repeats the approved fixed30 comparison against the normally installed
candidate. Both arms are archived from verified commits. No runtime is patched
by the build or measurement driver. The harness, optional SQL instrumentation,
order, environment, count and analysis are pinned to the original comparison.

Use a fresh owned work directory with enough budget for source and Go caches.
Run under `scripts/experiment_disk.py` (8GiB minimum free,12GiB owned budget).
Do not compile or run another benchmark during the30 measurement suites.

```sh
python benchmarks/dictionary-installed/build.py --work-dir WORK --candidate CANDIDATE_COMMIT
python benchmarks/dictionary-installed/run.py --work-dir WORK
python benchmarks/dictionary-installed/analyze.py --raw WORK/evidence/observations.json --compact WORK/evidence/compact.json --summary WORK/evidence/summary.json
python benchmarks/dictionary-installed/analyze.py --compact WORK/evidence/compact.json --summary WORK/evidence/summary.json --check
```

The build uses sibling `../temp` for disposable Go caches. Preserve sources,
runner hashes, measurement plan/completion, host, compact observations and
summary; discard recreatable snapshots, binaries and caches when inactive.
All30 suites remain in the compact record; only4 warmups are omitted from the
primary comparison. No rerolls, tail exclusions or adoption decision are made.
