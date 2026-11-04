# Prisma 7 / mysql2 comparison spike

Darwin arm64, Node 24.22.1, Prisma 7.10.1, mysql2 3.24.6 and community
`@jsr/netscript__prisma-adapter-mysql` 0.0.8 (JSR revision 11).
This is an unofficial adapter comparison, not official Prisma mysql2 support
or a Node product acceptance claim. No runtime/product changes were made.

## Results

| Route | PASS | FAIL |
| --- | ---: | ---: |
| Prisma Client (27) + same-process Live Reset (1) | 23 | 5 |
| Direct mysql2 controls | 6 | 1 |

The five Prisma failures have three causes:

- BigInt: default driver conversion rounds 9007199254740993 to 9007199254740992.
- DateTime: default local timezone interpretation shifts the UTC fixture by nine hours.
- Bytes: the adapter converts Buffer to a base64 string; Prisma expects a byte array
  (P2023). This also breaks nested_create and relation, giving three failed cells.

Direct mysql2 with `supportBigNumbers: true`, `bigNumberStrings: true` and
`timezone: 'Z'` reads the exact BigInt, UTC date and Buffer. Python SQL also
reads the exact stored values. The additional control invokes the pinned
adapter conversion and observes the base64 string. These isolate driver
configuration/adapter conversion causes; they do not require a mariamem SQL fix.
The direct-driver failure deliberately records the unsafe default BigInt conversion.
Potential adapter fixes are safe numeric options, explicit timezone semantics and
passing Bytes in Prisma's expected representation. Those fixes were not implemented.

Unfiltered count/findMany, aggregate/groupBy, raw zero-parameter queries and
Live Reset pass here. The earlier MariaDB-driver comparison had 1/28 passing
with defaults and 23/28 with pipelining disabled, but its five remaining failures
were different (prepared-statement interoperability). This route does not close
#93/#94/#95. No concurrent-load, native-MariaDB baseline or cross-platform
qualification was performed.

## Evidence and reproduction

Actual host and matrix source: `623804d0693153fd03a0a46b19bad98db8b534bd`.
Product baseline: `5ed63f12561ca8644815fac54653a8e618900f3f`.
Earlier MariaDB matrix source: `e7e575b6528d2e608da2fc9b3f700e53da5101a9`.
The evidence commit adds documentation/control source only; it was not the host build.
See [matrix JSON](evidence/matrix.json), [35-cell CSV](evidence/results.csv)
and [type controls](evidence/type-control.json). Binary checksum and clean
VCS build stamp are in the matrix JSON. Lockfile pins the adapter and dependencies.

Use Node 24, Python 3.11 with pymysql and the repository's Python package.
Inspect source identity with `scripts/git_identity.py` before building. Build a
clean, stamped host (`go build -trimpath -buildvcs=true -o HOST ./cmd/mariamem-host`;
a standalone clone was used because this Go version did not stamp nested worktrees).
Then, in this directory:

```sh
npm ci --no-audit --no-fund
DATABASE_URL=mysql://root@127.0.0.1:3306/prisma_matrix npx prisma generate
python matrix.py --host /absolute/path/to/HOST --output /absolute/path/to/results
```

`matrix.py` starts disposable mariamem endpoints and seeds each case independently.
For `type_control.mjs`, seed using `matrix.initialize(info, True)` and execute
its contents as Node module stdin in this directory with the `DB_*` environment
from `matrix.env_for(info)`. Record Python SQL string/HEX reads for the same row.
The exact executed control SHA256 is recorded in type-control.json.
Prisma CLI's previous 15 successful cases, including shadow migration and reset,
were not rerun: changing the Client adapter does not change those CLI paths.

Sources: [Prisma drivers](https://www.prisma.io/docs/orm/v7/core-concepts/supported-databases/database-drivers),
[community adapter](https://jsr.io/@netscript/prisma-adapter-mysql).
