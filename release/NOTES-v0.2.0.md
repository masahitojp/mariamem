# mariamem v0.2.0

Draft for the intended stable 0.2 release; final candidate acceptance and
publication remain pending. The intended Python distribution version is `0.2.0`.

## FAST prepared-state startup

This release completes the first FAST milestone for disposable real MariaDB
testing. Snapshot/Fork reuses prepared database state while creating an
independent guest/server for each fork. Per-test server disposal avoids the
need for application test code to reset schemas, roll back transactions or
delete data for isolation; connections and owned handles still need cleanup.

Startup uses prepared public test RSA keys for `caching_sha2_password`, carries
verified native identity within one startup call and runs independent
verification with two bounded workers. The plugin remains enabled, required
integrity checks remain intact and default grant bypass is unchanged. These
keys are non-secret test infrastructure, never production credentials; this
does not add full public account/grant authentication support.

## Reference performance and limitations

On a fixed **MacBook Air M1 / 16 GiB / macOS 27.0 arm64**, 30 independent
diagnostics-OFF Go trials measured Fork through the first successful SQL with a
prepared 1,000-row fixture: **374.2 ms p50, 417.7 ms p95, 446.1 ms max**.
The fixed-reference p95 <500 ms milestone passed. These are reference
observations, not hardware-independent guarantees or a universal hosted-CI
threshold. See the [method and exact source/artifact identities](https://github.com/masahitojp/mariamem/blob/9dc577d/benchmarks/final-v02-local-reference.md).
Hosted runner variability makes CI a correctness/regression monitor.

Memory remains substantial. The ×16 probe measured about **259 MiB per DB on
macOS** (incremental physical footprint) and **327 MiB on Ubuntu** (incremental
PSS). Both platforms completed ×16 and left no runtime residue after teardown
in measured scenarios. Memory efficiency is not solved; restore and larger
memory/storage architecture work remain outside this release.

The [practical Testcontainers comparison](https://github.com/masahitojp/mariamem/blob/9dc577d/benchmarks/practical-suite-comparison.md)
found fresh-container/server isolation much slower, but sharing a server with
schema reset much faster for repeated tests. Those workflows have different
isolation guarantees and used different MariaDB versions/defaults. Fork did
not materially outperform fresh mariamem Start for the small fixture. Two
fresh-container 100-test attempts failed in that benchmark environment; no
general reliability conclusion follows. This is not a universal winner claim.

## Sessions and lifecycle

The current guest supports 16 independent sessions; this is not a permanent
API capacity guarantee. One DB with 16 simultaneous clients passed session
isolation, reconnect and cleanup. The 17th session receives recoverable MySQL
1040. Normal Go pool use does not require `SetMaxOpenConns(1)`; concurrency does
not imply throughput scaling. Session variables, temporary tables and
transactions remain independent.

Interrupted active SQL invalidates the whole Database, including other
connections. Close it and start or fork another instance. Snapshot is cold,
rejects unfinished transactions and consumes its source on success. Server-side
prepared statements remain unsupported. Public lifecycle semantics are unchanged
from the prior release; 0.x API compatibility is not a 1.0 stability guarantee.

## Platform and distribution

Supported platforms remain **macOS 15+ / arm64** and **Ubuntu 24.04 LTS /
x86_64**, requiring SSE2 + SSSE3 on Ubuntu. Clean release validation uses
macOS 15 and Ubuntu 24.04 with **Go 1.26.8 / Python 3.14**. Package minimums
are not a broad tested language matrix. Other Linux distributions, Linux arm64,
macOS Intel and Windows are unsupported; `linux_x86_64` is not a manylinux claim.

Go uses the public module plus an explicit native bundle; Python wheels include
the runtime. Neither user path requires Docker. Final assets will include both
native bundles, both wheels, platform-qualified corresponding-source archives
and SHA256SUMS, bound to exact candidate acceptance. No PyPI publication is
part of this release path. Project code is GPL-2.0-only; bundled components
retain their separate terms, including Wasmer Singlepass BUSL-1.1.

ORM/framework and dbt compatibility, AI-generated CRUD-test ergonomics and
CoW/runtime-sharing designs are not claimed by v0.2.0. They remain later
validation/exploration work.
