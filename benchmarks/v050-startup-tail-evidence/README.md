# v0.5.0 startup-tail evidence

The [report](../v050-startup-tail.md) owns interpretation. This directory
preserves the raw suite records, reducers, source identities, and the selected
stack proof. `SHA256SUMS` verifies the files, excluding itself. All guest/SQL
oracles were the repository's existing OwnedPrepared and Python product-suite
oracles; neither was weakened. No trial was dropped or retried on failure.

`samples.jsonl` is the first *sequential* plain/diagnostic pilot campaign. It
identified a time-order confound and is intentionally excluded from the final
frequency table. `paired-10mib.jsonl` is the balanced 60-block Go campaign;
`python-paired-10mib.jsonl` is the 60-block Python campaign. One JSON line is
one four-DB suite, with all four ready durations. `paired-summary.json` and
`python-summary.json` are outputs of `reduce.py` and `reduce_python.py`.
`stack-probe-full.txt` is a single 250 ms diagnostic sample, never counted in
frequency. `stack-excerpt.txt` selects its relevant root/page-cleaner goroutines;
`stack-probe-trace-*.json` contain the matching host/guest startup records.

Reconstruction used the exact released tag object and source commit in the
report, Go1.26.8 on macOS arm64, and these binary SHA-256 identities:

| Binary | SHA-256 | Role |
| --- | --- | --- |
| unchanged `ownedprepared` | `528e8aa0e28b563d960e3a472d6e117617972ea58178dcee1411e28ba6aca244` | Go plain frequency; matches Product Verification |
| unchanged `mariamem-host` | `b2b8a9e88e238ede252d8290897b269ce7c09823e6fd9622fdb9a0dcde48dc66` | Python frequency; matches Product Verification |
| diagnostic `ownedprepared-spike` | `de75d6bce5734cc9c3544d23810662763d8d6a6af141b4a6327157bb171b412d` | Go startup phase location, balanced against plain |
| diagnostic `ownedprepared-stack` | `0207958cdd8aa1b95d5cc0075a22617f16a4664afa09c27c9e970d0b9ac1c0c3` | One stack sample only |

The temporary workspace layout was `experiment-work/startup-tail-v050/{worktree,temp,evidence}`.
The unchanged binaries were built at the released source with:

```sh
GOTOOLCHAIN=go1.26.8 CGO_ENABLED=1 go build -p 1 -trimpath -buildvcs=false \
  -o ../temp/ownedprepared ./benchmarks/ownedprepared
GOTOOLCHAIN=go1.26.8 CGO_ENABLED=1 go build -p 1 -trimpath -buildvcs=false \
  -o ../temp/mariamem-host ./cmd/mariamem-host
```

The first diagnostic binary was built from the released source plus
[`phase-reader.patch`](phase-reader.patch), which adds the private-MemFS timing
reader. The experiment branch additionally contains a 250 ms one-shot
`runtime.Stack` sample used only for the stack binary. The stack binary is
never substituted for either frequency arm. Within that workspace, the exact capture commands
were `python3 ../temp/paired.py`, then
`/private/tmp/mariamem-v050-release-venv/bin/python ../temp/python_paired.py`
with the repository's disk guard. The scripts in this directory are copies of
those task-local files and expect that layout. `inputs*.json`,
`python-inputs.json`, `experiment.json`, and the two console logs retain
environment, command and successful-run receipts. A new workspace should
check tag/source/binary identities before repeating the campaign.
