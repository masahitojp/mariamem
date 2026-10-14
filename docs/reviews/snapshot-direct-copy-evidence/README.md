# Direct-copy evidence

See the [Human Review](../snapshot-direct-copy-spike.md). Numerical results and
command output are preserved; local paths are replaced by `<experiment-work>`,
`<repository>` and `<user-home>` placeholders. `.log` source names are archived as `.txt` to respect
the repository publication boundary. Empty process logs are omitted; their zero
length and hashes remain in [archive-index.json](archive-index.json). The archive
index maps original names to retained names, records both pre-normalization and
archived SHA256, and identifies every changed file. Trailing whitespace in two text logs is
removed for clean diffs. Replay scripts are unmodified.

## Replay layout

Use a new disposable experiment workspace with a 6 GiB budget and at least 8 GiB
free-space reserve. Keep the original evidence intact. The scripts expect:

```text
<work>/worktree/       clean measured commit for verification
<work>/temp/source/    independent clone of that commit, .git directory
<work>/temp/*.py       copies of scripts/ from this evidence directory
<work>/temp/venv/      Python 3.14.8, pytest 9.1.1, pymysql 1.2.3
<work>/temp/gocache/   disposable Go build cache
<work>/temp/go-tmp/    disposable compiler temp
<work>/temp/tmp/       disposable runtime temp
<work>/evidence/       new replay output
```

Both source directories must be clean at
`3341f99000246fc64ae17b4ea39118f55589de1e`. Resolve it as a commit with
`python3 scripts/git_identity.py inspect HEAD` before any build. Use Go 1.26.8
and native macOS arm64; build scripts set GOMAXPROCS=2, local cache/temp paths,
`MARIAMEM_TEST_DEFAULT=1` and the experimental route. An available Go toolchain
and downloaded modules are prerequisites; setup/download time is not benchmark
time. The standalone clone avoids the observed linked-worktree VCS stamp mismatch.

Run in order, under `scripts/experiment_disk.py` with those disk limits:

1. `python3 <work>/temp/verify-build.py` — verification; on these fixed inputs
   stops at the known `verify.py check` publication-boundary failure. Inspect that
   exact failure and the earlier checks; do not accept any arbitrary failure.
2. `python3 <work>/temp/build-only.py` — correctly stamped standalone-clone builds
   and a real-guest integration subset. Validate host buildinfo against the exact
   measured commit using the `git_identity.verify_go_binary` Python helper
   (the campaign script shows its benchmark invocation; use the host path for
   the host check). This helper is not a command-line subcommand.
3. `python3 <work>/temp/python-check.py` — three original Python route checks.
4. `python3 <work>/temp/guard-campaign.py` — validates benchmark buildinfo with
   `verify_go_binary`, performs all 34 runs, writes raw records and summary. Uses
   a 1,200-second limit and 5-second disk checks. It requires the preceding
   command receipts; its named exception for canonical-check is specific to this
   recorded historical failure, not a general quality gate waiver.
5. `python3 <work>/temp/analyze.py` — compact derived comparison.

Do not re-run into the original evidence/trace directories: trace directories
must be new. Replay numbers can differ; compare identical logical inputs and
interpret the small sample honestly. Resource and trace runs remain separate
from ordinary medians. Retain all failures and sample records.

The final `verification.json`, `builds.json`, `python-check.json` and
`measurement-inputs.json` are authoritative for the measured commit. Files
prefixed `initial-`, `trace-attempt-` and `worktree-` document superseded attempts;
`console.txt` is the early unit run. They must not be counted as final source
verification or additional performance samples.
