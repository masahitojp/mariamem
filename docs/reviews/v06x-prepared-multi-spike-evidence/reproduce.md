# Reproduce the bounded continuation

The report pins guest source 926365bdc853bd2a45cc00139db1b64c5d78e3e9 and
tested host source 7037f05bb279de4ce7aab622e33b13e20d7c52f0. Inspect both with
scripts/git_identity.py, not a tag-object/commit guess. Use an experiment
workspace, 32 GiB budget and 16 GiB free-space floor; put caches/output in temp.
TASK below is its absolute root. Commands are functional checks, not benchmarks.

## Guest and Go

1. At the pinned guest source, seed the Docker-mounted build area with the
   tracked build/go.mod. The initial run omitted it and the source guard correctly
   rejected the hidden tracked file; that failure is retained. Execute the
   retained `executed-final-guest-command.sh` with the workspace disk guard.
   It invokes the official build_generated_guest.py --development-output route
   in the fixed builder, with a fresh /root SDK and /work. Match its absolute
   TASK/source mounts to your workspace. Canonical archive hashes remain in locks.
2. Inspect final-guest-record.json, final flags/link/CMake records, phase trace
   and final-strict-patch-reapplication.json. The latter independently applies
   both patches with --fuzz=0 and matches the actual builder files and authored
   include. No source-to-Wasm same-input two-build claim is made here.
3. At the tested host source, regenerate into fresh outputs twice:

   ```sh
   python scripts/regenerate_release_guest.py --development --guest-dir "$TASK/temp/final-guest" --output "$TASK/temp/repro-a"
   python scripts/regenerate_release_guest.py --development --guest-dir "$TASK/temp/final-guest" --output "$TASK/temp/validated-native"
   ```

   Use Python 3.14 as below, GOTOOLCHAIN=go1.26.8 and task-local
   GOCACHE/GOMODCACHE/GOTMPDIR. The actual first translation preceded the new
   exact binding and failed installation; retain that receipt as FAIL. Its raw
   candidate was subsequently used in the independent comparison.
4. SHA256 every relative file in translation/module. Match 52 source/data files.
   To compare full installation including provenance, use one identical input
   record with the official installer for the independent candidate:

   ```sh
   python scripts/generate_runtime.py --source-module "$TASK/temp/repro-a/candidate/module" --development-input "$TASK/temp/validated-native/installation-inputs.json" --output "$TASK/temp/common-a"
   ```

   Compare its 99 relative files with validated-native/product/internal/generatedgo.
   Do not normalize or rewrite original provenance; distinct path-containing
   installation records legitimately hash differently. Inventories are retained.

## Python and native reference

The successful interpreter is standalone CPython 3.14.8, OpenSSL 3.5.9; its
distribution URL and observed binaries are recorded. With task-local uv cache
and Python install directory, use `uv python install 3.14.8 --no-bin` to avoid
creating a launcher outside the disposable task. Create a venv; install exactly
mysql-connector-python==26.7.0, PyMySQL==1.2.3 and pytest==8.4.2. See freeze and
cp314 wheel SHA256. The original uv-created launcher into this task was removed;
no task launcher should remain after cleanup.

Do not add ssl.PROTOCOL_TLSv1 or alter connector code. The same 26.7.0 import
under Homebrew 3.14.8/OpenSSL 4.0.3 should retain the recorded AttributeError,
separately from the successful interpreter. Do not call this all Python 3.14 failing.

Set PYTHONPATH to validated-native/product/python. Run each with --host set to
the explicit generated binary and --output set to its JSON destination:

- tests/v06_multi_scenarios.py
- tests/v06_prepared_extended.py
- benchmarks/spikes/prepared-bridge/scenarios.py
- tests/v06_prepared_error_health.py
- tests/v06_default_connector_probe.py

No --no-multi-statements option is passed. The last probe specifies neither
use_pure nor client_flags, uses prepared=True and ordinary %s parameter markers.
The mode contrasts separately exercise pure and C extension defaults.

Start a disposable MariaDB 12.3.3 reference from
`mariadb@sha256:805c8e104bd563d5bfa24fadd3f31cd419ea859cb5277f32b5dbf2db714f9ed1`,
empty local root password/test database, port 127.0.0.1:57009. Run the same probes
with --port rather than --host. Stop the owned reference afterward. This Linux
arm64 container does not count as native Ubuntu x86_64 acceptance.

**Keep nonzero results.** The multi fixture still reports the procedure setup
FAIL (mysql.proc missing), and the original C-extension syntax oracle still
fails expecting1064/getting2006 on both engines. Health/pass findings do not
erase either failure. The native-unknown-option packet was observed before
PyMySQL raised its normal exception; no packet/error semantics were changed.

## Go and J1

In the generated product, use Go1.26.8 and task-local caches/temp:

```sh
go test -p 1 -trimpath ./internal/mysqlwire
go run -p 1 -trimpath ./tests/v06_prepared_probe --output guest.json
go run -p 1 -trimpath ./tests/v06_prepared_probe --dsn 'root@tcp(127.0.0.1:57009)/test?parseTime=true' --output native.json
```

Package actual generated lifetime functions with tests/v06_prepared_thread_fixture.py
--product <generated-product> --output <fresh-fixture>. In its module run
go test -p 1 -trimpath -count=1 -v ./probe with JOIN_PROTECTED=0/JOIN_BACKING=heap:
expect the early-free canary165→1 FAIL and passing controls, not merely exit1.
Then JOIN_PROTECTED=1, heap/mmap, each with and without -race: all four cases PASS.
The host-only validator did not change 98 runtime/code files or copied fixture
inputs; reuse was verified explicitly in validated-j1-reuse.json.

The full developer route provides its own SQL/transaction/Snapshot/three-Fork/
shared-host cleanup smoke. Input-origin and exact-binding mutation checks are
tests/test_dev_guest_tools.py and tests/test_thread_lifetime_binding.py (34).
Full Qualification, installed-wheel/framework acceptance and performance are
separate; all these developer artifacts remain UNQUALIFIED.
