# Issue93: zero-parameter EXECUTE interoperability

The candidate accepts an optional single boolean new-parameter-types flag
(`00` or `01`) after the nine-byte zero-parameter COM_STMT_EXECUTE body.
The existing canonical body remains accepted. Any other byte, multiple suffix
bytes, unsupported cursor or invalid iteration remains rejected. Nonzero
parameter decoding, statement ownership, guest code and query-input monitoring
are unchanged. This fixes the MariaDB Node driver's zero-parameter form without
loosening the packet decoder to ignore arbitrary trailing data.

Runtime candidate source_commit: `c7a0e97feb942763b4920a10f29060918ab9bcaf`.
Base source_commit: `df75666e3e46f6ebd4e2541c89586ad7b43275f9`.
The later documentation/evidence commit does not change tested product code.
The test first failed against the base decoder on optional byte00; both decoder
and wire packages then passed, including malformed input not reaching the engine
and a following valid execution on the same statement.

## Native behavior and deliberate limit

[Native packet evidence](native.json) comes from Linux arm64 MariaDB
`12.3.3-MariaDB-ubu2404`, Docker image ID
`sha256:23ccfa2f2df26837c8f397a8f9a070ad728768c095d246edd07cd8d24e9ec40c`,
registry digest
`mariadb@sha256:805c8e104bd563d5bfa24fadd3f31cd419ea859cb5277f32b5dbf2db714f9ed1`.
All seven zero-parameter shapes returned exact binary row7 and a healthy
following SELECT11: no suffix,00,01,02,ff,0100 and arbitrary ASCII suffix.

The [protocol documentation](https://mariadb.com/docs/server/reference/clientserver-protocol/3-binary-protocol-prepared-statements/com_stmt_execute)
places the type flag inside the positive-parameter-count branch. This is a
client-interoperability extension, not a claim that the documented canonical
zero-parameter packet requires the extra byte. Native MariaDB ignores more
trailing data than this candidate intentionally accepts. Only the defined
boolean flag values are supported; arbitrary native permissiveness is not copied.
The existing nonzero-parameter flag validation already accepts only0/1.

## Prisma and driver acceptance

Pinned reproduction source_commit:
`604a0c588f0a602bf6ea67d811b97bae2748c3ea`, directory
`benchmarks/spikes/prisma-dogfood`, using its package-lock, schema and matrix.ts.
Node24.22.1, Prisma/client/official adapter7.10.1, mariadb3.5.4.
Always `pipelining:false`; no diagnostic WHERE workaround.

| Case | Native12.3.3 | Candidate macOS arm64 |
| --- | --- | --- |
| unfiltered findMany | PASS | PASS |
| unfiltered count | PASS | PASS |
| aggregate | PASS | PASS |
| groupBy | PASS | PASS |
| zero-parameter raw query | PASS | PASS |
| filtered count control | PASS | PASS |
| parameterized raw control | PASS | PASS |

[Native Prisma](prisma-native.json) / [candidate Prisma and raw controls](prisma-candidate.json).
The candidate report includes actual clean Go1.26.10 VCS stamping and binary hash.
The native report's source_commit identifies the caller's source helpers, not
the native server source; the native server is identified by image/version above.

Both endpoints also pass two repeated driver `execute('SELECT 1')` calls,
parameterized execute and following text query on the same connection.
The real candidate accepts no suffix/00/01;02/ff/0000/0100 return1835 followed
by healthy SELECT11 and CLOSE/PING. Unit tests retain cursor/iteration rejection,
short-header bounds and all invalid single-byte flags2..255. Existing complete
preparedproto/mysqlwire package tests retain positive-parameter and long-data
validation; the wire regression proves rejected suffixes never call the guest.

## Reproduce

Build a clean, stamped candidate using `scripts/git_identity.py` first; this
run used a standalone clone for Go VCS stamping. Restore the pinned prior
Prisma spike into a disposable directory, run `npm ci --no-audit --no-fund`
and `DATABASE_URL=mysql://root@127.0.0.1:3306/prisma_matrix npx prisma generate`.
Then use [acceptance_probe.py](acceptance_probe.py):

```sh
python acceptance_probe.py --source /path/to/clean/candidate \
  --prisma /path/to/prior/spike --host /path/to/stamped/host --output candidate.json
```

For native mode, start the fixed image with a fresh temporary data directory,
local-only published port and empty test root password; use `--native-port PORT`
instead of `--host`. Native mode recreates prisma_matrix in that disposable DB.
[native_probe.py](native_probe.py) takes SOURCE,NATIVE_PORT,NATIVE_IMAGE_ID,
NATIVE_IMAGE_DIGEST,NATIVE_OUTPUT environment variables and replays the seven
raw variants. These probes reuse the repository's existing raw-wire readers.

#94 default pipelining and #95 last-statement alias remain separate and unresolved.
This local acceptance is scoped to #93; it is not both-platform installed-wheel
qualification, complete Prisma support, publication approval or a performance
claim. No heavy Release CI or permanent Node acceptance job was added.

## Local verification

[Validation summary](validation.json): complete preparedproto/mysqlwire tests,
canonical `verify.py check --profile daily` and `verify.py smoke` pass on the
runtime candidate above. The broad Python phase reports1847 passed/92 skipped;
source oracles run separately before Go. Skipped optional/runtime profiles are
not newly claimed as accepted. Python Live preserves cap2 capacity timeout and
busy behavior, and Go Live preserves busy/closed-parent refusal and reset state.
An initial wire-test fake omitted mandatory Affected/InsertID strings; the fake
was corrected before these final checks. No production error was hidden.
