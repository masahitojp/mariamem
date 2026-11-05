# Node ORM connection settings

For TypeORM and MikroORM tests, start with their **MariaDB dialects** when
connecting to mariamem's local MySQL-protocol endpoint. These are configuration
examples based on bounded dogfood, not a Node SDK or blanket ORM support claim.
The recorded run used Node24.22.1, TypeORM1.1.2, MikroORM7.2.7 and mysql2 3.24.6
on macOS arm64. Those historical runs are not acceptance of the published 0.6.2
artifacts or Ubuntu. Use the [published packages](../README.md#installation);
0.6.2 adds prepared-driver fixes and [bounded pipelining](mysql-protocol.md).
The separate [Prisma recheck](../release/NOTES-v0.6.2.md#configuration-guidance-and-validation-scope)
retains its own source/version/platform limits.

## Own the database outside Node

A [Python](python.md#share-preparation-isolate-mutations) or
[Go](go.md#low-level-database-lifetimes) test owner starts or forks the database
and passes its connection information to the Node process. Set `DB_HOST`,
`DB_PORT`, `DB_USER`, `DB_PASSWORD` and `DB_NAME` from that test-owned endpoint;
keep the returned empty password when applicable. Create the application database
and prepare its schema explicitly before application queries. An ORM connection
setting does not create that database.

The following fragments assume the application's existing entity definitions
and environment variables above. Use the normal ORM initialization and close
methods; no special mariamem driver or single-connection restriction is needed.

## TypeORM

Install `typeorm`, `mysql2` and `reflect-metadata`. Select `mariadb` even though
both TypeORM's MySQL and MariaDB dialects use mysql2:

```ts
import 'reflect-metadata';
import { DataSource } from 'typeorm';
import { User, Post } from './entities.js'; // Your application's entities.

const db = new DataSource({
  type: 'mariadb',
  host: process.env.DB_HOST,
  port: Number(process.env.DB_PORT),
  username: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
  entities: [User, Post],
  timezone: 'Z', // Example convention: fixtures store UTC DATETIME values.
  synchronize: false, // Prepare the schema separately.
});

await db.initialize();
try {
  // Run application tests.
} finally {
  await db.destroy();
}
```

Choose a timezone matching the application's data convention. In the recorded
UTC fixture, TypeORM's default local interpretation shifted a fixed DATETIME by
nine hours; `timezone: 'Z'` preserved it. This controls client conversion and
does not mean every application should reinterpret existing local dates as UTC.
See TypeORM's [MySQL/MariaDB connection options](https://typeorm.io/docs/drivers/mysql/).

## MikroORM

Install matching versions of `@mikro-orm/core` and `@mikro-orm/mariadb`. Import
`MikroORM` from the MariaDB package rather than `@mikro-orm/mysql`:

```ts
import { MikroORM } from '@mikro-orm/mariadb';
import { User, Post } from './entities.js'; // Your application's entities.

const orm = await MikroORM.init({
  host: process.env.DB_HOST,
  port: Number(process.env.DB_PORT),
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  dbName: process.env.DB_NAME,
  entities: [User, Post],
});
try {
  // Run application tests using a request/test-owned EntityManager.
} finally {
  await orm.close(true);
}
```

MikroORM7's MariaDB driver uses mysql2 internally while retaining MariaDB-specific
JSON/schema handling. See its [v7 migration guide](https://mikro-orm.io/docs/upgrading-v6-to-v7)
and [connection configuration](https://mikro-orm.io/docs/configuration).

## Reset, cleanup and evidence boundaries

Before Live Reset or Snapshot capture, finish application work, close the ORM
pool and wait for physical connections to retire through the owning API.
Reinitialize the ORM after Reset; do not keep a stale EntityManager/client.
Close the Node client before closing its test-owned DB. The recorded Live cases
closed pools, reset and reconnected in the same Node process with a stable endpoint.

The [pinned dogfood report and110-case inventory](https://github.com/masahitojp/mariamem/tree/1630e7fa/benchmarks/spikes/node-orm-dogfood)
cover bounded CRUD, relations, transactions, seeded type reads, schema changes
and Live Reset. MikroORM's MariaDB profile passed27/27. TypeORM's MariaDB profile
passed26/27 with the default timezone; its separate UTC datetime control passed.
A complete TypeORM27-case rerun with UTC was not performed. The configuration
fragments above are adapted examples, not separately executed application tests.

MySQL dialects showed JSON/check/default/schema-diff differences. These are
recorded in [#108](https://github.com/masahitojp/mariamem/issues/108); no native
server comparison established them as mariamem wire defects, and MySQL8 SQL
parity is outside this work. ORM CLI/migration lifecycles, full upstream suites,
other versions/platforms and performance remain unqualified. No additional
runtime changes or permanent CI jobs are required by this guide.
