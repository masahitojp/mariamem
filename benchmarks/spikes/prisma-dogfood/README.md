# Prisma dogfood — issue #92

**Continue investigation: ordinary Prisma Client use still fails on current
mariamem.** Migration succeeds. With pipelining disabled and parameterized counts,
the bounded CRUD/type/Live lifecycle probe succeeds. This is a diagnostic result,
not adoption, Node SDK support or general Prisma compatibility.

Executed source_commit: `9648e8b3820b89632e11ec4521ef6c9d033520d9`.
Product baseline: `bc00b8e66e5fd57bc9b2127001faf8e05952b417` (#91).
Only this experimental consumer changes; runtime/guest/API/version inputs stay
unchanged. [Compact receipt](results/darwin-arm64.json) retains actual versions,
clean Go build stamps, binary hash and the three conditions. The npm lock is a
reproduction input; generated clients, npm/Go caches and raw logs are disposable.

| Condition | Observed result |
| --- | --- |
| Prisma7.10.1 + adapter7.10.1 + mariadb3.5.4, adapter-owned pool of2, default pipelining | `migrate deploy` PASS; nested create FAIL2013, unexpected client input during running query |
| Same with `pipelining:false` | migration and nested create/seed PASS; unfiltered `user.count()` FAIL1835 |
| Same plus diagnostic positive-id filters on counts | CRUD, relation reads, FK cascade, transaction commit/rollback, Decimal/BigInt/DateTime/JSON/NUL/binary round trips PASS; same Node PID survives disconnect/Live Reset/reconnect and sees restored baseline |

The direct-driver control confirms text `SELECT 1` and parameterized
`execute('SELECT ?',[1])` work, while `execute('SELECT 1')` fails1835 and leaves
the connection usable. `internal/preparedproto/values.go` rejects every trailing
byte when parameter count is zero. The pinned MariaDB driver writes a
new-parameter-types flag even for zero parameters (`lib/cmd/execute.js`,
`sendComStmtExecute`). Code comparison explains the observed boundary; a native
MariaDB reference has not been run. Default pipelining is enabled by the pinned
driver; `internal/mysqlwire/wire.go:callGuest` deliberately aborts on input while
SQL runs. Disabling pipelining removes that first failure in this probe.

Next product decisions are separate: narrow zero-parameter execute compatibility
with positive/negative wire controls, and an explicit policy for Node driver
pipelining. Do not weaken the disconnect/abort guarantee to make this probe pass.
`migrate dev`/shadow databases, other OS/versions, performance and persistent CI
are unverified and are not implied by this result.

## Reproduce

Use a clean, identity-checked standalone clone on the experiment branch, within
the repository's disposable-workspace/disk budget process. Nested worktrees can
produce missing Go VCS stamps with this toolchain; use a standalone checkout of
the exact same commit for the host if the strict binary check rejects it. Do not
fabricate a stamp or bypass verification.

From repository root, with a Python environment containing PyMySQL:

```sh
python scripts/git_identity.py inspect HEAD
GOTOOLCHAIN=go1.26.10 go build -p 1 -trimpath -buildvcs=true -o build/prisma-host ./cmd/mariamem-host
cd benchmarks/spikes/prisma-dogfood
npm ci --no-audit --no-fund
DATABASE_URL=mysql://root@127.0.0.1:3306/prisma_dogfood ./node_modules/.bin/prisma generate
python run.py --host ../../../build/prisma-host --output ../../../build/prisma-default
PRISMA_PIPELINING=off python run.py --host ../../../build/prisma-host --output ../../../build/prisma-off
PRISMA_PIPELINING=off PRISMA_PARAMETERIZED_COUNTS=1 python run.py --host ../../../build/prisma-host --output ../../../build/prisma-diagnostic
```

The first two probe invocations intentionally return nonzero on this source;
run them separately. The third reports `PASS_DIAGNOSTIC_PARAMETERIZED_COUNTS`,
never unconditional PASS. The direct-driver fingerprint currently asserts the
known zero-parameter failure; update that oracle deliberately when implementing
a fix. The Node process is launched with `node --import tsx` to avoid tsx CLI
IPC path limits in deeply nested temporary directories. Prisma8's RC was not
selected even though the registry's latest tag pointed to it.

Initial setup attempts exposed tsx's long Unix-socket path limit and missing Go
VCS stamps. They are harness/environment failures, not Prisma SQL failures. The
three retained conditions above were rerun with one correctly stamped binary.
No product changes, Release CI invocation or automated acceptance job was added.


## Expanded matrix, including shadow databases

Executed source_commit: `e7e575b6528d2e608da2fc9b3f700e53da5101a9`.
[All71 cells](results/matrix-darwin-arm64.csv) and [metadata/oracles](results/matrix-darwin-arm64.json)
record **39 PASS /32 FAIL**, using one separately initialized mariamem instance
per cell so a fatal query cannot hide later failures.

| Group | PASS | FAIL |
| --- | ---: | ---: |
| Prisma CLI |15|0|
| Default-pipelining Client + Live |1|27|
| Pipelining-disabled Client + Live |23|5|

CLI validation/generation, db execute/push/pull, migrate deploy/status/reset,
automatic and explicit-shadow `migrate dev`, create-only migrations, schema diff,
shadow-based migration diff, and resolve applied/rolled-back all passed. The reset
was initially blocked by Prisma's AI guard; after the Human explicitly consented,
it was rerun against a newly created throwaway DB and passed. Data disappearance
and migration reapplication were checked. The schema-diff cell deliberately adds
a column and expects the documented exit code2 for a nonempty diff. Development commands used an actual
PTY, not a non-interactive invocation that would produce a misleading failure.
No production database or preexisting user database is a target.

Failures are tracked for v0.6.2:

- #93: five pipelining-disabled cells fail1835 on zero-parameter execution:
  unfiltered findMany/count, aggregate/groupBy and zero-parameter raw query.
- #94:24 default cells hit the query-in-progress input abort; one transaction-array
  cell reports EPIPE. That EPIPE's relationship to pipelining is inferred from
  the contrast (the identical operation passes with pipelining disabled).
- #95: two default cells hit1243 for statement ID0xFFFFFFFF. A separate sequential
  prepare/execute control (no pipelining) succeeds with the real ID and fails
  with the alias, leaving the connection healthy. The exact control source is
  [retained](alias_control.py), with its hash in the metadata.

Prisma Client connect alone passes in default mode. With pipelining disabled,
filtered reads/counts, writes, nested writes, createMany, upsert, relations,
nullable values, interactive/array transactions, expected unique errors,
parameterized raw SQL, all five type projections and same-process Live Reset
pass. This is the explicitly listed matrix, not every API/version/platform in
the upstream Prisma test suite. Native MariaDB comparison is still unexecuted.

To reproduce the matrix in the same clean experimental workspace layout:

```sh
python benchmarks/spikes/prisma-dogfood/matrix.py --host HOST --output OUTPUT
```

Provide explicit user consent to Prisma's dangerous-AI-action guard for the reset
cell. That consent is passed through `PRISMA_USER_CONSENT_FOR_DANGEROUS_AI_ACTION`;
the earlier messages are not silently reused as consent. All CLI case files and
generated outputs live in ignored `.matrix/` scratch. Only compact rows and
selected assertions are retained; no raw full-stack logs enter Git.
