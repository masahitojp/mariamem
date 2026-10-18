# Reproduce the bounded prepared spike

Use source commits in the report, `scripts/git_identity.py inspect`, the pinned
toolchain/locks and a disposable experiment workspace with 32 GiB budget and
16 GiB free-space floor. Set TASK to that workspace, work in its experiment
worktree, and keep all outputs/caches in TASK/temp. Logs retain original paths;
substitute your own TASK. Commands below summarize the executed stages; failed
attempts remain separately recorded. Do not run against production data.

1. At guest source 13e253f, run the committed
   `benchmarks/spikes/prepared-bridge/guest-command.sh` through the workspace
   guard. It uses `build_generated_guest.py --development-output`, pinned Docker
   builder, pinned source locks and `guest/experimental.patch`. See guest JSON,
   patch-application evidence, build flags/CMake cache and phase logs.
2. At host source e305ac9 and independently 30ab38e, run
   `scripts/regenerate_release_guest.py --development --guest-dir "$TASK/temp/dev-guest" --output "$TASK/temp/dev-native-a2"`
   (use a fresh output dev-native-b for the second). Confirm exact CLI with
   `--help`; logs/phase records retain the executed stages. Use Go 1.26.8,
   task-local GOCACHE/GOMODCACHE/GOTMPDIR. A2 smoke failed on a stale fixture;
   B uses the corrected fixture. Keep that distinction.
3. Compare raw translation/module inventories. To compare provenance as well,
   run the official installer on each independent candidate with the same
   installation record (no hash normalization):

   ```sh
   python3 scripts/generate_runtime.py --source-module "$TASK/temp/dev-native-a2/candidate/module" --development-input "$TASK/temp/dev-native-b/installation-inputs.json" --output "$TASK/temp/common-input-a2"
   python3 scripts/generate_runtime.py --source-module "$TASK/temp/dev-native-b/candidate/module" --development-input "$TASK/temp/dev-native-b/installation-inputs.json" --output "$TASK/temp/common-input-b"
   ```

   SHA256 every relative file; compare 52 raw and 99 installed files. Preserve
   the original distinct provenance files too. `independent-regeneration.json`
   contains inventories and the sole original-route difference.
4. Install pinned consumer dependencies recorded in python311-freeze.txt; use
   Python 3.11. Run the committed `tests/v06_prepared_extended.py --host <host>
   --output <json>` once with defaults and once with `--no-multi-statements`.
   Run `benchmarks/spikes/prepared-bridge/scenarios.py` similarly. Keep failing
   cases; these programs return nonzero if any assertion fails. Executed
   supported-flag script snapshots are retained because the CLI option was
   added after the initial contrast runs. Only the flag differs, not SQL or
   prepared mode. Set PYTHONPATH to the staged product/python.
5. Start the exact native MariaDB image in fixed-inputs.json with a temporary
   root/test database. Run the same scripts with `--port` instead of `--host`.
   Run reference.py and executed-reference-expanded.py for metadata. Stop the
   owned reference container afterward.
6. Copy the authored tests/v06_prepared_probe into the generated product, then
   `go run -p 1 ./tests/v06_prepared_probe --help` to confirm options. The actual
   guest run uses no native port, `--output <json>`; native control uses the
   `--dsn "root@tcp(127.0.0.1:57009)/test?parseTime=true"`. This runs direct guest and Go DB/Tx/Conn cases.
7. Run `tests/v06_prepared_thread_fixture.py --product <staged-product> --output
   <fresh-j1-fixture>`. In its module run `go test -count=1 -v ./probe` with
   JOIN_PROTECTED=0 JOIN_BACKING=heap: expect the recorded early-free failure,
   not a passing test. Then JOIN_PROTECTED=1, heap/mmap, each with and without
   `-race`: expect all four controls PASS. Preserve exact log/identity records.

No second source-to-Wasm build, general shared-memory proof, native Ubuntu run,
full compatibility campaign or performance benchmark is claimed by these commands.
All experimental developer outputs remain UNQUALIFIED.
