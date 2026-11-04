# TypeORM / MikroORM official mysql2 dogfood

Bounded manual spike on Darwin arm64, Node24.22.1, TypeORM1.1.2,
MikroORM7.2.7 and mysql2 3.24.6. Both official ORM MySQL and MariaDB dialects
use the same pinned mysql2 driver. No community Prisma adapter is involved.
No product/runtime/guest/version/CI changes were made.

## Final results

27 independent cases per profile, plus two explicit TypeORM UTC controls:

| Profile | PASS | FAIL |
| --- | ---: | ---: |
| TypeORM `type: 'mysql'`, default timezone | 25 | 2 |
| TypeORM `type: 'mariadb'`, default timezone | 26 | 1 |
| MikroORM `@mikro-orm/mysql` | 24 | 3 |
| MikroORM `@mikro-orm/mariadb` | 27 | 0 |
| TypeORM MySQL, datetime only with `timezone: 'Z'` | 1 | 0 |
| TypeORM MariaDB, datetime only with `timezone: 'Z'` | 1 | 0 |

Total: 110 final cells, 104 PASS /6 FAIL. These are bounded authored checks,
not the complete upstream suites or a product support declaration.

The cases cover connect/count/find, create/bulk/nested create, relation/update/
upsert/cascade/null, transaction commit/rollback, duplicate-key rejection,
seeded BigInt/Decimal/DateTime/JSON/Bytes reads, raw queries with and without
parameters, aggregate/group-by, schema create/no-op diff/column expansion,
and same-process disconnect -> Live Reset -> reconnect.
Type checks read fixed SQL-seeded values; they are not a complete type write/read
matrix. Nested create exercises ORM writes of a smaller typed object.

## What failed, and what worked

- TypeORM datetime (both dialects): local timezone interprets the fixed UTC
  DATETIME as local time, shifting by nine hours on this host. Explicit
  `timezone: 'Z'` passes both affected controls. This is an explicit UTC-fixture
  convention, not proof that every application's datetime semantics require UTC.
- TypeORM MySQL no-op schema diff: repeatedly proposes changing nullable `name`.
  MariaDB dialect sees no drift and passes the same test.
- MikroORM MySQL JSON: returns JSON text instead of an object for the MariaDB
  JSON column. The MariaDB driver returns the expected object.
- MikroORM MySQL no-op diff: proposes nullable-default and JSON/check-constraint
  changes immediately after its own schema creation.
- MikroORM MySQL schema update: that diff tries to drop check `meta`, failing
  with "Can't DROP CONSTRAINT". With the MariaDB driver, no-op detection and
  actual varchar120 ->140 expansion both pass.

Thus the observed compatible starting point is TypeORM `type: 'mariadb'`
(with an explicit timezone matching the fixture convention) and MikroORM's
`@mikro-orm/mariadb`. The remaining MySQL-profile failures are dialect/metadata
interoperability observations; a native MariaDB counterpart was not executed,
so they are not classified as confirmed mariamem-specific defects.
No wire failures 1835/2013/1243 from the earlier Prisma/MariaDB-driver experiment
appeared in these final cases. Both ORMs preserve the tested BigInt, Decimal
and Bytes values. Live Reset passes all four profiles, with the same Node PID,
stable endpoint and restored baseline after closing the ORM pool before Reset.

## Evidence and reproduction

Executed host and final matrix source_commit:
`ba34bb25225a664d315d2605f899727b8d30a511`.
Product baseline_source_commit: `df75666e3e46f6ebd4e2541c89586ad7b43275f9`.
The evidence commit is later and was not the host build source. Lockfile pins
all dependencies. [Matrix JSON](evidence/matrix.json) includes the binary hash,
clean Go VCS stamp, every case and control; [CSV](evidence/results.csv) is the
110-row inventory. Selected Live protocol logs preserve the same-PID evidence.

Use Node24 and Python3.11 with pymysql and this source's `python/` package.
Inspect source using `scripts/git_identity.py` before building. This run used
Go1.26.10 and a clean standalone local clone to obtain a real VCS stamp, because
this Go version did not stamp the nested worktree correctly:

```sh
go build -p 1 -trimpath -buildvcs=true -o HOST ./cmd/mariamem-host
```

In this spike directory, install with `npm ci --no-audit --no-fund`, then run:

```sh
python matrix.py --host /absolute/path/to/HOST --output /absolute/path/to/results
```

Run from a clean source checkout matching HOST; the runner rejects a dirty,
wrong-source or unstamped binary. Each cell starts a fresh disposable mariamem
instance, avoiding contamination from preceding failures. Schema cases start
with an empty DB; other cases use baseline.sql plus fixed SQL seed. Connections
are never made to an external DB. Schema update uses a new MikroORM instance
with the changed entity definition. Live has a separate JSON control channel
with ORM debug logging disabled so buffered logs cannot cause false timeouts.

Initial runs exposed harness errors (removed MikroORM6 persistAndFlush API,
raw query-builder fragments, metadata mutation and log/control mixing). A second
run also lacked dialect-separated report labels. Those runs are retained as
local diagnostic history, excluded from this final table. The final source fixes
these issues and executes all 110 cells; it does not patch ORMs to hide failures.

Out of scope: ORM CLI/migration generation/up/down, other relations and column
families, worker concurrency, cancellation, performance, native MariaDB baseline,
other OSes or ORM/Node versions, and permanent acceptance/CI integration.

Primary references:
- [TypeORM MySQL/MariaDB options](https://typeorm.io/docs/drivers/mysql/)
- [MikroORM quick start and drivers](https://mikro-orm.io/docs/quick-start)
- [MikroORM7 API changes](https://mikro-orm.io/docs/upgrading-v6-to-v7)
- [MikroORM query builder](https://mikro-orm.io/docs/query-builder)
