# Clean macOS 12 arm64 acceptance harness

This harness does not edit `release/review.json`. A successful run produces
reviewable evidence; setting `platform_acceptance=true` remains a separate action.
Run inside a clean macOS 12 arm64 VM with Python 3.9+ and Go 1.26.8 installed.
Network access is needed for the public Go module and its pinned MySQL driver.
No Wasmer, MariaDB, Homebrew runtime, or repository checkout is needed in the VM.

Copy these files to one directory in the VM, preserving the subdirectory:

```text
platform_acceptance.py             (from scripts/)
platform_acceptance/consumer.go     (from scripts/platform_acceptance/)
mariamem-native-darwin-arm64.tar.gz
```

From that directory:

```sh
python3 platform_acceptance.py \
  --archive ./mariamem-native-darwin-arm64.tar.gz \
  --sha256 7fe851bdab2fafef1dffd2607a8af41b880a1a539c6e37be25b11c7f1aa8c8c2 \
  --module 7f4820e220e757c4a171bb02622b03eb3fbc0613 \
  --evidence ./macos12-arm64-acceptance.json
```

The example pins the candidate prepared in Task 9c and its Go source commit.
That source commit must be publicly retrievable from GitHub before running;
otherwise `module_fetch` fails. Use an explicitly chosen published revision if
reviewing a different candidate. There is no local `replace` fallback, automatic
push, or runtime download. Supply a new expected hash when the archive changes.
An existing evidence/log file is never overwritten; choose a new filename for
another attempt. `--go /absolute/path/to/go` selects an installed Go executable.

The runner checks the archive checksum before safe extraction and verifies
executable permissions, the native manifest hashes, and guest sidecar. It creates
a temporary external module with isolated Go caches, disables workspace and
ambient Go settings, fetches the public module and MySQL driver v1.9.3, and builds
the companion consumer. Only the extracted directory is passed as
`Options.NativeDir`; no repository-native lookup exists.

The consumer uses `SetMaxOpenConns(1)` and text-protocol DSN compatibility. It
checks Start, database/sql, SELECT 1, MariaDB version, InnoDB engine and committed
transaction, disconnect, temporary snapshot, source closed, A/B forks and row
isolation. Cleanup closes pools/databases/snapshot, checks closed state and removes
temporary snapshot/runtime directories. Snapshot is preceded by pool Close and
WaitDisconnected. Step results are written as they arrive, including failures.
The harness then removes the extracted archive, external module and its caches.

## Evidence

Keep both generated files:

- `macos12-arm64-acceptance.json`: exact `sw_vers` output, architecture, Go version,
  requested/resolved module identity, archive filename/SHA256, runtime/guest hashes,
  MariaDB version, step results, final `PASS`/`FAIL`, and
  `platform_acceptance_passed`.
- `macos12-arm64-acceptance.log`: Go command output and consumer stderr.

A failure has `failure.step`, per-step error information, and a nonzero exit
status. Unexecuted steps remain `NOT_RUN`. Abrupt VM/power loss can leave the
last persisted `RUNNING` step; it must not be interpreted as a pass. Successful
environment checks only establish OS/architecture; the human must ensure the VM
is clean. No automatic release approval is performed.

## Development validation only

Append `--dry-run` and choose a separate evidence filename to check environment
capture, checksum, extraction, permissions and artifact hashes without module
fetch or guest execution. This permits the development macOS 27 host, always
reports `DRY_RUN`, and always sets `platform_acceptance_passed=false`.
A normal run rejects anything except macOS major version 12 and arm64 before
fetching/running the consumer. Unit tests mock target environment information;
those tests are not platform acceptance.

```sh
python3 -m unittest discover -s tests -p 'test_platform_acceptance.py'
go build -o build/platform-acceptance-consumer ./scripts/platform_acceptance
go vet ./scripts/platform_acceptance
```

After actual VM success, review the evidence against the intended archive hash,
then perform the separate Task 9c review update. Until then the review stays
`guest_source=true`, `runtime_notices=true`, `platform_acceptance=false`.
