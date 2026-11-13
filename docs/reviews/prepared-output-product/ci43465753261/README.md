# Installed distributions43465753261 — PASS

Exact candidate d0aca17352708c5cb85812e0f4c11b228d3006e7 passed both macOS15
arm64 and Ubuntu24.04 x86_64. Each platform built an exact-source private frozen
wheel and consumed it from an isolated installation; external Go module consumers
used the exact-source private proxy. Existing Go/public Snapshot/failure/lifecycle,
installed Python, GORM32 and SQLAlchemy44 cases pass. Go1.26.10 and forward
compatibility Go1.27.3 both executed. No package or release was published.

The first macOS job failed to acquire a hosted runner (capacity annotation),
before executing checkout or project code. Its rerun passed. Ubuntu passed on
the first attempt. This is not a runtime repair or a product failure.

`acquisition.json` records artifact IDs, raw archive/entry hashes and source-home
prefix normalization. `consumers.json` is parsed without changing values from the
complete report printed in `consumers.txt`; only the leading Go download message
is excluded. The workflow mistakenly treated its report output file as a
directory, so its separate report/log were not copied. The complete structured
report survives in stdout, but the unretained detailed log is not reconstructed
or claimed available. The workflow now copies the actual report and sibling log
for future submissions. Wheel source inventory/manifests/hashes and build output
are retained; the wheel binary itself was not uploaded. Prior canonical exact
regeneration provides the rebuild path, not permanent binary availability.

This gate does not replace same-condition performance or any remaining explicit
prepared packet/limit acceptance. Earlier CI receipts retain their original SHAs.
