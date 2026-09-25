# Diagnose Start EOF without changing production behavior

This tool was created for the unsupported macOS 12 guest-start investigation.
Keep it for on-demand startup diagnosis; it is not part of ordinary development,
release acceptance, or supported-platform verification. The VM example below is
historical and does not establish support for macOS 12–14.

## Launch path

For a fresh `mariamem.Start`, `mariamem.go` creates a temporary
`mariamem-go-*` directory and its `runtime/` subdirectory (mode 0700).
`internal/host.Start` creates `mariamem-transfer-*`. `internal/guest.Start`
launches exactly these argv entries:

```text
<NativeDir>/wasmer-headless
run
<NativeDir>/mariamem.wasmu
--no-tty
--volume
<transfer-directory>:/snapshot-out
```

The executable/module paths are absolute. Environment is `os.Environ()` with
`WASMER_DIR=<mariamem-go-temp>/runtime` appended (last value wins). There is no
other production environment override and `cmd.Dir` is not set: the child
inherits the caller's working directory. The process starts in a new process
group (`Setpgid: true`). stdin and stdout are pipes; no request is written before
the unsolicited ready frame. stderr is a pipe copied into the supplied writer.
The MySQL TCP listener is created only after guest readiness.

When invoked by the clean-platform harness, the caller has its isolated Go/cache
and TMPDIR settings, filtered ambient runtime variables, and the external consumer
directory as cwd. These are inherited by production launch, not set by guest.Start.
The diagnostic's `--acceptance-env` repeats that harness policy with fresh paths.
It does not claim to recover the now-deleted paths/environment of a previous run.

## Why the error alone loses information

`mariamem.Start` passes `&db.logs` as stderr writer. This holds only the last
16 KiB. On startup failure Start returns `nil, error` and removes its temporary
directory; callers have no Database handle with which to call `Logs()`.

The guest reader uses `io.ReadFull` for the length-prefixed JSON frames. EOF calls
`readFailed` then `Abort`, which sends SIGKILL to the process group. `cmd.Wait()`
records `exitErr` internally, but the returned startup error is the original
reader error. Thus EOF can obscure both stderr and the original exit status.
No production change is made by this diagnostic.

## VM command

Copy only `scripts/diagnose_guest_start.py` alongside the already verified
candidate archive, then run in the macOS 12 VM:

```sh
tar -xzf mariamem-native-darwin-arm64.tar.gz
mkdir -p diagnostic-caller
python3 diagnose_guest_start.py \
  --native-dir "$PWD/mariamem-native-darwin-arm64" \
  --cwd "$PWD/diagnostic-caller" \
  --acceptance-env \
  --output "$PWD/start-diagnostic" \
  --timeout 120
```

Use a new output directory for every attempt. Python 3.9+ is sufficient; Go and a
repository checkout are not required. The NativeDir must be explicitly supplied;
there is no runtime lookup or fallback. No tracing/backtrace variables are added.
Without `--acceptance-env`, the script inherits its current environment.
Alternatively, `--environment-json caller-env.json` accepts an exact saved caller
environment mapping; `--cwd` supplies the caller working directory. The diagnostic
still creates fresh lifecycle directories and overrides WASMER_DIR as production
does.

The output directory contains:

- `result.json`: actual executable/argv/cwd, runtime/guest hashes, PID, readiness,
  natural vs diagnostic-induced termination, raw returncode, exit code or signal.
- `environment.json`: exact environment passed to this child, saved mode 0600
  inside a mode-0700 output directory. It may contain inherited credentials;
  inspect/redact before sharing. Do not post this file automatically.
- `stdout.bin`: unmodified binary stdout, including any framed readiness response.
- `stderr.log`: full child stderr, without the production 16 KiB truncation.

The diagnostic keeps stdin open and sends no request during startup. EOF or an
invalid frame does **not** trigger the host's immediate SIGKILL: the child may
finish naturally, preserving its actual status and stderr. Once a valid ready
frame is observed, or on timeout, the diagnostic sends SIGTERM to the process
group, then SIGKILL if needed after five seconds. These interventions are recorded
in `diagnostic_signals` and `stop_reason`. A SIGTERM caused by `ready_observed` is
not a native startup failure. Created runtime/transfer directories are removed
when the diagnostic finishes; capture files remain. A pre-spawn failure records
`diagnostic_error` with null exit status and empty output files.

Share `result.json` and `stderr.log` first; retain `stdout.bin` for protocol
inspection. Running `--version` successfully establishes that the runtime can
launch, but does not execute the AOT guest. The remaining boundary is module
loading/AOT execution/WASIX guest initialization through readiness. The VM's
captured stderr and natural exit status are needed to narrow it; no root cause
is asserted from EOF alone.

## Development check

Six inert-process unit tests cover exact argv/environment construction, delayed
stderr after stdout EOF, natural exit code, readiness-triggered termination,
timeout, spawn failure and invalid output. The development macOS 27 run reached
the API v2 ready frame and was intentionally stopped with SIGTERM. This only
validates the diagnostic; it is not macOS 12 acceptance. All review flags and
release candidate bytes remain unchanged.
