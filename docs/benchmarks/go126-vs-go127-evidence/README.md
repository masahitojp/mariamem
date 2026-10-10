# Exact-source toolchain comparison evidence

Source80a37385f9d1eda6604358dd5ba2235feb0b26ca, Go1.26.8 versus1.27.2.
444 measured four-test suites plus18 excluded warm-ups. Raw directory includes
both; trial99 is warm-up. Do not pool warm-ups or separately profiled20-DB runs.
Every normal trial/compiler/mode has30 observations; heavy has6.
statistics.csv/json include p50/p95/min/max, ratio-of-p50 delta and paired bootstrap.
The two effect estimators differ: confidence bounds belong to paired trial medians,
not ratio of p50s. All children/SQL observations in a process are clustered together.

## Reproduce

Create an experiment-workspace, min free12 GiB/budget12 GiB. Check out **the measured
source commit**, not the later report commit. Copy build.py/profile.py/summarize.py
from this evidence directory to sibling evidence (outside the pinned source tree).
Require a clean source, verify it with scripts/git_identity.py and compare matched
production trees in environment.json. Get the official Go1.27.2 darwin-arm64 archive,
verify the SHA256 in builds.json, unpack to sibling temp/sdk1272. Set GO1268_BIN to
an installed exact Go1.26.8 executable. Its `go version` is checked by build.py.

From worktree cwd, with no competing benchmark/build:

```sh
python3 ../evidence/build.py
python3 benchmarks/ownedprepared/toolchain_compare.py
python3 ../evidence/summarize.py
python3 ../evidence/profile.py
```

Localhost listen and OS counters need ordinary host permissions; sandbox-denied
listen is a setup error, not a compatibility failure. The runner refuses to overwrite
existing successful output; start from fresh performance output directories.
The scripts use task-local compiler/module caches, same flags, exact runtime version
checks, direct compiled binaries, explicit disk guards, timeouts and ABBA order.
Use the same runtime env and hardware scope as campaign/environment. Reproduction
collects new timings; it cannot promise identical timings or noise.

Profiles: top25 CPU/alloc_space text and diagnostic-run counters committed here.
The eight small original `.pprof` samples are retained with hashes in local
`build/experiment-work/v046-go-performance/evidence/` as selected unique evidence.
They are not binary release/source-distribution inputs. Re-run profile.py to collect
new profiles. Original benchmark binaries, SDK archive/extraction and caches are
disposable; their hashes/build info identify accepted measurement bytes.

The builder's final recorded times use populated caches. Initial prefill was not a
controlled cold-build comparison; none of these build costs enter runtime tables.
No GOEXPERIMENT attribution or Go1.26.9 run was performed. The report explains why.

After collecting and committing compact evidence, finalize/cleanup via the existing
experiment-workspace helper. KEEP only unique evidence/refs, not rebuilt workspace.
SHA256SUMS covers committed files; profile-checksums.json covers retained originals.
