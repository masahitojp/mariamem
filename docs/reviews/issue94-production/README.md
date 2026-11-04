# Issue #94 production acceptance

The Human approved the bounded policy on 2026-11-05 JST. The product extraction
is based on main `69186d7d4b01fdb1d5ec9318b37bbc3681bb2c22`, after Issue #93
merged through CI 41866270670. It contains no experiment-only overlay or header
trace. The [decision](../../decisions/issue94-bounded-pipeline.md) and
[protocol guide](../../mysql-protocol.md) own the limit and overflow behavior.
Protected PR CI/integration and Release qualification are separate from these
local results.

Runtime source_commit `999ff7fd244aa0c924c063cffbda02ae73ba9a05` was inspected with
`scripts/git_identity.py` and built in a standalone clean shared clone with
Go 1.26.10, `go build -p 1 -trimpath -buildvcs=true`. The binary stamp is unmodified
and its digest is in [prisma.json](prisma.json). Later commits change tests/docs
only; the product runtime bytes are identical.

On Darwin arm64 / Python 3.11, the following passed:

- Prisma 7.10.1 / official adapter 7.10.1 / mariadb 3.5.4 / Node 24.22.1:
  all 27 existing Client cells plus same-process Live Reset, 28/28 with the
  driver's default pipelining. This includes nested create and unique-error
  handling, the two outstanding Issue #95 normal-driver acceptance cells.
- Real `tests/test_python_wire.py`, normal idempotent Close and multiclient
  controls: 25/25. New controls cover ordered effects/responses, queued invalid
  sequence, EOF, overflow, query deadline and owner Close, including independent
  roots after fatal failures.
- `go test -race -p 1 ./internal/mysqlwire ./internal/preparedproto -count=1`.
- `scripts/verify.py check --profile daily`: Go tests/vet, source/policy checks,
  1,847 Python passes, 97 explicit skips and 92 subtests. Runtime opt-in tests are
  skipped by this owner and are covered by the separate real-host run above.
- `scripts/verify.py smoke`: Python DB/Snapshot/Fork/Live and Go Live source checks.

[validation.json](validation.json) binds command cohorts, source identities,
limits and full-log checksums. The first real-host attempt used SLEEP(20) with
one-second shutdown and failed cleanup in three new controls. It did observe
EOF/overflow as expected; it did not establish prompt forced disposal. The final
controls use SLEEP(0.5) and a busy barrier, preserve cause/unusable/independent-root
assertions, and test cooperative cleanup. Timeout is a separate 0.1-second case.
No disposal oracle or runtime behavior was relaxed to convert that result.

For reproduction, use the [source-pinned Prisma project and matrix](https://github.com/masahitojp/mariamem/tree/604a0c588f0a602bf6ea67d811b97bae2748c3ea/benchmarks/spikes/prisma-dogfood).
Install its lockfile/generate the client, run the existing 27 `RUNTIME` cells via
`matrix.initialize(info, True)` / `matrix.env_for(info, False)` and its
`live_case(host, False, output)` against the stamped product host. False here means
"do not disable pipelining"; `PRISMA_PIPELINING` is absent. Fresh disposable DBs
are used for each cell. CLI migration/shadow commands were not rerun because
this change addresses the Node Client transport boundary.

The old [spike](https://github.com/masahitojp/mariamem/blob/253b03d269859cfb2d713f2cae18ea5b22f499c2/docs/reviews/issue94-bounded-pipeline/README.md)
retains the 47 header observations and its own original source, not product
acceptance. Existing fixture drift and negative mutation checks remain active.
Daily CI detects focused Go/buffer/admission regressions and inventory drift;
real TCP controls stay with the existing Release integration owner. No Node CI
job is added. Local results do not establish Ubuntu, installed consumers, general
ORM compatibility, whole-process RSS/performance, or Release READY.
