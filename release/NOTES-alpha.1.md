# mariamem v0.2.0-alpha.1

The first public 0.2 FAST alpha integrates two measured startup improvements for
disposable real MariaDB databases. The Python distribution version is `0.2.0a1`.

## First FAST tranche

- `caching_sha2_password` loads an embedded, fixed RSA-2048 test keypair instead
  of generating fresh keys on every startup. The pair is public, non-secret test
  infrastructure and must never be used for production credentials. The plugin
  remains enabled; default `skip-grant-tables` and public connection behavior
  are unchanged. Missing or invalid keys fail startup with diagnostics.
- Go carries verified native artifact identity through one startup call,
  eliminating two redundant AOT hash scans. Every startup still verifies its
  native bundle and snapshot integrity. There is no global or persistent trust
  cache; the separate Python host retains independent validation.

## Measured isolation latency

The canonical Go benchmark uses a prepared 1,000-row InnoDB fixture and measures
Fork → first successful SQL. On macOS arm64, ×1 p50 improved from approximately
1,224 ms in the historical v0.1-style baseline to 517 ms in the accepted main
baseline. The new Ubuntu ×1 p50 is 539 ms. These are observations from different
hosted CI runs, not a paired release comparison or a performance guarantee.
See the [baseline analysis](https://github.com/masahitojp/mariamem/blob/559885f/benchmarks/fast-tranche-baseline.md)
for the recorded results, concurrency,
CPU/RSS limitations and acceptance evidence.

0.2 FAST is not complete. Restore remains the next investigation; this alpha
makes no restore/storage change, and each database still has substantial memory
cost. The exploratory latency targets are not release promises.

## Connection and lifecycle semantics

The current guest supports 16 independent MariaDB sessions, with recoverable
MySQL error 1040 at capacity; this is not a permanent API guarantee. Session
variables, temporary tables and transactions remain isolated. Normal Go pool
usage does not require `SetMaxOpenConns(1)`; concurrent execution does not imply
performance scaling.

Interrupted active SQL makes the entire Database unusable, including its other
connections. Close it and start or fork another instance. Snapshot rejects an
unfinished transaction in any session; successful Snapshot consumes its source.
Prepared-key callback acceptance does not add full public account/grant
authentication support.

## Platform and distribution

Support remains macOS 15+ / Apple Silicon arm64 and Ubuntu 24.04 LTS / x86_64
(SSE2 + SSSE3). Other Linux distributions, Linux arm64 and Windows are outside
scope. Validation remains Go 1.26 and Python 3.14; the Linux wheel uses
`linux_x86_64`, without a manylinux claim.

Go users supply the native bundle through `Options.NativeDir`; there is no
automatic download. Python wheels include the runtime. This is an alpha and
APIs/packaging may change. Assets include both platform-native bundles, wheels,
platform-qualified corresponding-source archives and SHA256SUMS. Project code
is GPL-2.0-only; dependencies retain their licenses/notices. No PyPI publication
is performed.
