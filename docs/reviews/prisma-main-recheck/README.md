# Prisma recheck after Issues #93 / #94 / #95 merged

On 2026-11-05 JST, the Human requested another Prisma validation. The complete
previously listed 71-cell matrix passed against merged main source_commit
`c27061f1a33eed2908fd90b0e2d816692e001339`: **71 PASS, 0 FAIL**.
No runtime overlay, diagnostic count workaround or product change was used.

| Group | Earlier PASS / FAIL | Main PASS / FAIL |
| --- | --- | --- |
| CLI | 15 / 0 | 15 / 0 |
| Default-pipelining Client + Live | 1 / 27 | 28 / 0 |
| Pipelining-disabled Client + Live | 23 / 5 | 28 / 0 |
| Total | 39 / 32 | 71 / 0 |

The earlier comparison is the source-bound matrix at `e7e575b6`, product baseline
`bc00b8e6`; it is not a new run on that older binary. All previously failing cells
now pass on main. [results.csv](results.csv) lists every cell;
[metadata.json](metadata.json) pins full source identity, binary digest/stamp,
input hashes, versions, expected nonzero CLI exits and same-process Live results.

Darwin arm64, Node 24.22.1, Prisma/client/official adapter 7.10.1, mariadb 3.5.4,
Go 1.26.10, Python 3.11.18 and PyMySQL 1.2.3. Source identity was inspected with
`scripts/git_identity.py`; a clean standalone shared clone built the host using
`go build -p 1 -trimpath -buildvcs=true`. `verify_go_binary` checked the exact main
commit and unmodified stamp before consumption. Each cell creates a fresh
throwaway DB; no existing user or production DB is used.

CLI covers validate/generate, db execute/push/pull, migrate deploy/status/reset,
automatic and explicit shadow migrate dev, create-only, schema diff, migration
shadow diff and resolve applied/rolled-back. Development commands use a real PTY.
Reset checks data removal and migration reapplication. Schema diff's exit 2 and
the deliberately invalid migration's exit 1 are expected assertions, not failures.
The Human's explicit disposable-reset consent was passed to Prisma's AI guard.

Each Client mode covers the original 27 CRUD/relation/transaction/raw/error/type
cells. Both Live cells retain the same Node PID, disconnect before Reset, reuse
the same endpoint, and verify the restored baseline after reconnection. Default
mode leaves `PRISMA_PIPELINING` absent; off mode sets it to `off`.

Reproduce using the [fixed project and lockfile](https://github.com/masahitojp/mariamem/tree/604a0c588f0a602bf6ea67d811b97bae2748c3ea/benchmarks/spikes/prisma-dogfood):
`npm ci`, generate Client, and run its `matrix.main(host, output)` with `ROOT`
pointing to the clean main checkout and the stamped host above. Retained local
`evidence/run_matrix.py` wires those paths and records the new baseline identity.
The original SQL/TypeScript assertions are unchanged.

This is a finite manual dogfood on macOS. Ubuntu, installed artifacts, other
Prisma versions, community mysql2 adapter, TypeORM/MikroORM, performance and Release
qualification were not run. No new CI job or blanket Node support is implied.
