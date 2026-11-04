# Dub dogfood on mariamem

Dub's existing Playwright **API project passes 84/84, with zero skips/retries**
against mariamem main `c27061f1a33eed2908fd90b0e2d816692e001339` on macOS arm64.
No product, guest, SDK, version or CI change was needed. This is manual finite
application acceptance, not a declaration that every Dub feature is supported.

| Boundary | Result |
| --- | --- |
| Unmodified 40-model schema, `prisma db push` | PASS; 40 tables |
| Repeated `db push` | PASS; already synchronized |
| Unmodified upstream development seed | PASS |
| Harness assertions using upstream client and application functions | 19/19 |
| Upstream PrismaPlanetScale HTTP adapter through local proxy | PASS |
| Upstream Playwright `api` project, Turbopack + preparation | 84/84; 0 skipped, 0 flaky |

[Final API rows](results/api.csv), [compact provenance and DB cases](results/metadata.json)
and [first complete Webpack diagnostic](results/cold-api.csv) preserve separate
cohorts. API coverage includes customers, pagination, domains/JSON fields,
folders, bulk link updates, Shopify request handling, tags, UTM and workspaces.
The 19 harness-defined checks call unchanged `getLinksCount`,
`getLinksForWorkspace`, the Prisma singleton and Playwright workspace setup,
with additional relation/BigInt/JSON/transaction/constraint/cascade assertions.
They are not presented as 19 upstream tests.

## Sources and preparation

- Dub source_commit `6b463b4bdd9ed2fd9aa416f67b5b77d317b1471e`.
  [Upstream source](https://github.com/dubinc/dub/tree/6b463b4bdd9ed2fd9aa416f67b5b77d317b1471e)
  and its lockfile/schema/app source remain unchanged. Archive and 25 selected
  input hashes are retained. Only our `.mariamem-*.ts` entry files are added to
  the disposable copy. Upstream source is not vendored into this report.
- Node 24.22.1, pnpm 9.15.9, Prisma/client/PlanetScale adapter 6.19.1,
  Next 15.5.8, Go 1.26.10, Python 3.11.18 and PyMySQL 1.2.3.
- Before building/consumption, `scripts/git_identity.py` and `verify_go_binary`
  verify the exact main commit. The clean standalone host clone uses
  `go build -p 1 -trimpath -buildvcs=true`; its stamp/digest are in metadata.
- Python owns a fresh disposable DB per cohort (`query_timeout=30`). Dub uses
  its original Prisma singleton without a pool/driver workaround. The schema
  uses `relationMode="prisma"`; cascade evidence is ORM behavior, not new SQL FK
  support. Dub's normal schema setup is `db push`, not a migration history replay.

Use an owned budgeted workspace with `worktree/`, `temp/host-source` at the main
SHA above, `temp/dub` extracted at the Dub SHA, `temp/mariamem-host`, `temp/venv`
and `evidence/`. Install Dub's frozen lockfile with scripts disabled, then run:

```sh
DATABASE_URL=mysql://unused:unused@127.0.0.1:1/planetscale corepack pnpm --filter web exec prisma generate --schema=./prisma/schema
corepack pnpm --filter @dub/utils build
corepack pnpm --filter @dub/ui build
```

Set up dedicated local Redis plus [serverless-redis-http](https://github.com/hiett/serverless-redis-http),
using token `local-dogfood-only` and loopback port 18079. Start the
[official QStash development server](https://upstash.com/docs/qstash/howto/local-development)
as container `mariamem-dub-dogfood-qstash`, exposing loopback port 18080, and save
its three displayed local test credentials to `evidence/qstash-local-env.json`.
Image digests are pinned in metadata. QStash's app target is the host-local
Docker gateway; no hosted credentials or public tunnel are used.

Copy `db-cases.ts` to `temp/dub/apps/web/.mariamem-dogfood.ts`, then:

```sh
python benchmarks/spikes/dub-dogfood/run.py --workspace TASK_WORK \
  --output TASK_WORK/evidence/final --redis-url http://127.0.0.1:18079 \
  --with-proxy --qstash-env TASK_WORK/evidence/qstash-local-env.json --prewarm
```

Replace `TASK_WORK` with the absolute workspace path. The runner starts the
pinned PlanetScale HTTP proxy on port 13900, forwarding real SQL to mariamem.
For mariamem's empty DB password, it uses the proxy's documented `-mysql-no-pass`
mode and a nonempty HTTP password. It starts Dub's standard **Turbopack** dev
server on loopback port 8888, precompiles 18 routes via unauthenticated GET,
and runs the unchanged API project with one worker, original 30-second test
limits, retries=0 and no fail-fast truncation. Preparation responses are not
counted as passing tests. The runner reaps Next/proxy/queue and closes the DB.
Redis and its REST proxy are task-owned and must also be removed afterward.

## Diagnostics and limits

Initial harness setup lacked Redis REST, an HTTP DB proxy and the built UI
package. Those attempts remain separate in metadata. A proxy-auth probe also
exposed its empty-password configuration requirement; the corrected real HTTP
query passed. The first Python collector had a duplicate database argument;
that collector error was corrected before application acceptance.

The harness initially chose nondefault Webpack instead of Dub's standard
Turbopack. One complete configured Webpack run had 81 PASS / 3 timeouts, with
68-second lazy compilation exceeding the unchanged 30-second test deadline.
Cache-only and explicit-prewarm Webpack diagnostics also timed out and were
interrupted; neither is a full PASS. They do not establish a mariamem regression
or an upstream Dub bug. The final cohort switches to the upstream bundler,
starts with a fresh DB/Redis/queue, prepares routes and executes all 84 tests.
No assertion, timeout, retry or application code was relaxed to report success.

`local-fetch-only.cjs` limits outgoing Node fetches to loopback and records
failures; it returns no fake responses. Tinybird is unavailable, so analytics/API
log delivery emits nonblocking warnings. Hosted analytics, Vercel services,
background-job completion, browser/billing flows, Vitest, full production build,
Ubuntu/installed artifacts and Release qualification are not accepted here.
Performance/RSS and arbitrary data scale are unmeasured. No heavy CI is added.
