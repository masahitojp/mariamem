# mariamem v0.4.1

v0.4.1 removes unused encoded macOS/Linux executable images from the generated-Go
module, together with their dead provisioning package, embed script and
image-only metadata checks. Normal generated-Go/direct-link execution, Python
host-only packaging and explicit verified legacy Wasmer fallback are unchanged.

The completed distribution experiment measured a comparable complete local
module zip of **115.22 MiB → 31.13 MiB** (72.98% smaller). This is a source
archive size result, not a runtime performance or wheel-size claim. See the
[distribution report](../benchmarks/v041-distribution-cleanup.md) for exact
inputs, checksums and validation limits.

Canonical generated MariaDB source, guest/input provenance, corresponding-source
requirements, NOTICE and THIRD_PARTY_LICENSES are preserved. SQL/session,
Close and cold Snapshot/Fork semantics are unchanged. No memory backing,
reclaim/soak or Snapshot optimization is included.

Supported release targets remain macOS 15+ arm64 and Ubuntu 24.04 x86_64,
with canonical Go 1.26.8 / Python 3.14 validation. This candidate is submitted
to publication-free Release CI verify; no tag or publication is authorized.
