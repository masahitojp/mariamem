# CI42652906053: checks passed, scratch cleanup failed

Source_commit `0f60415f3c8d3dcd8ee43a116f3d773acf38f7bf`,
[run42652906053](https://github.com/masahitojp/mariamem/actions/runs/42652906053).
**Overall FAIL**, preserved under this original source. Both OSes completed
`Exact-source bounded constructor and real-DB checks` successfully on Go1.26.10.
Both artifacts contain `result.json=PASS`, all6 expected outcomes, and matching
source identities; artifact ZIP digests and all internal SHA256SUMS were verified.
Ubuntu uses4KiB OS pages, macOS16KiB. These are bounded correctness results,
not performance measurements or product adoption.

Both jobs then failed in `Dispose owned scratch and checksum receipts`:
`rm -rf` could not remove Go's read-only downloaded module directories. This is
build-input cache disposal, distinct from the runtime image FD/mapping/scratch
cleanup checked successfully by the probe. The workflow failed before writing
`job-status.json`, which is absent from the artifacts. Do not treat the whole
workflow as PASS or relabel these receipts to a later source.

Correction: run `go clean -modcache` with GOMODCACHE explicitly pointing only to
this job's owned cache, then remove the remaining scratch as before. No runtime,
guest, generated layout or SQL oracle change. A local regression executes the
actual cleanup block with read-only directories, proves the old rm failure,
protects unrelated-cache/evidence sentinels, checks the missing-cache path, and
preserves an earlier failed-job status. It also runs in the submitted workflow.
The new exact-source hosted result remains separate.

`assessment.json` keeps the compact source/run/job/artifact identities, digests
and results. Raw CI ZIPs remain outside tracked source; no full runtime rebuild
was performed locally for this workflow-only correction.
