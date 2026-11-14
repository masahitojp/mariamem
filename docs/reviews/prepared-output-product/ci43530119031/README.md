# Fixed host installed distributions43530119031 — PASS

Both macOS15 arm64 and Ubuntu24.04 x86_64 passed the existing exact-source private
wheel/external-Go-module acceptance on ef4d5cd97f718ebaaa5b2fa0d7999e3e6b169b9e.
Go/default, Snapshot/failure/lifecycle, installed Python, GORM32 and SQLAlchemy44
pass. Primary Go1.26.10 and compatibility Go1.27.3 executed; exact source inventories,
wheel manifests/hashes, commands and complete consumer logs are retained.
No public package, tag or release was created.

The previous retention bug is fixed: the actual report file and sibling log
both survive in this artifact. The duplicate JSON printed in stdout was checked
equal to the saved report, then reduced to its leading toolchain message plus
raw hash and extraction recipe. Reports are not synthesized from status labels.
acquisition.json binds archive/entry hashes and path-prefix normalization.
Canonical guest/C/generated input remains identical to43450619130; the new host
only removes redundant JSON decoding. This is installed-consumer evidence, not
release Qualification or the remaining selected-route Human disposition.
