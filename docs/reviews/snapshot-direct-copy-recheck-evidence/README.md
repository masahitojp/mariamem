# Eight-run follow-up evidence

See the [judgment](../snapshot-direct-copy-recheck.md). Raw numeric JSON results
are preserved. Local paths become `<experiment-work>`, `<repository>` or
`<user-home>`; trailing text whitespace is removed. `archive-index.json` records
original/archive hashes and all omissions (empty process output only).

The preserved `scripts/recheck.py` expects the same layout as the
[original replay instructions](../snapshot-direct-copy-evidence/README.md): clean
standalone `<work>/temp/source` at measured commit
`3341f99000246fc64ae17b4ea39118f55589de1e`, `temp/gocache`, `temp/go-tmp`,
`temp/tmp`, and `evidence`. No Python test venv or earlier test receipts are
needed for this follow-up. Copy both archived scripts into `<work>/temp/`.

With Go 1.26.8 and native macOS arm64, run `python3 <work>/temp/guard.py`.
Localhost bind must be permitted. The wrapper guards 6 GiB owned usage and an
8 GiB free-space reserve at 5-second intervals, with a 2,400-second total limit.
The runner allows 1,500 seconds for compilation, 900 seconds for the fixed
campaign and 180 seconds per scenario. It fails closed on source mismatch,
build/scenario failure or wrong child counts. Start with empty evidence output;
do not overwrite the archived results. No extra trials or outlier removal occur.

`build.json`, `inputs.json`, `campaign.json`, `summary.json`, eight per-run JSONs
and `guard.json` are final receipts. `sandbox-attempt/` contains the failed
permission attempt and is excluded from the eight timing trials. Replaying the
scripts reproduces the protocol, not guaranteed identical times or binary bytes
across different build paths. This tool is measurement support, not a release gate.
