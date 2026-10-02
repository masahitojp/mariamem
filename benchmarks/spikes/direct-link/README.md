# Direct-link architecture probe

Investigation only; production runtime remains unchanged. The template is `.go.txt`
so normal package discovery does not compile the probe. `prepare.py` copies the
canonical host adapter (only package declaration changes) and records its hashes.
All generated guest functions are imported directly from canonical source.

```sh
python3 benchmarks/spikes/direct-link/prepare.py --output build/directlink-probe
cd build/directlink-probe
GOTOOLCHAIN=go1.26.8 go build -p 1 -mod=mod -trimpath -o probe .
cd ../..
python3 benchmarks/spikes/direct-link/run.py \
  --work build/directlink-probe --output build/directlink-probe/evidence.json
```

This runs 3 functional campaigns (two sequential instances, then two simultaneous
instances) and two separate fault probes. Fault probes intentionally exit the
harness process. Normal execution uses per-instance pipes, WASI/FS/Module/Threads,
without native guest image materialization or a guest subprocess. The command
adapter's global diagnostic flag is set once before any worker starts.

Optional existing-executable control needs installed Python mariamem + PyMySQL,
an existing accepted generated host executable and localhost listener permission:

```sh
build/sqlalchemy-dogfood/py314/bin/python \
  benchmarks/spikes/direct-link/shared_executable.py \
  --host build/mariamem-host --output build/directlink-probe/shared.json
```

No cache, library lifecycle fix, ready heap restore or production API integration
is implemented. The first io.Pipe attempt's zero-length write deadlock is described
in the report; the final probe uses ordinary OS pipes within its own process.
``ready_ms`` is a secondary New-to-ready observation, not a public first-SQL
benchmark. No cross-platform direct-link acceptance or race-detector claim.


## Production acceptance diagnostic

`futex-precheck-race.go.txt` calls the unchanged generated `p7.Fn88` (WASIX futex
precheck) against the unchanged atomic CAS helper on one module's linear memory.
It returns mismatch before any host import: no SQL, server, FD, page cleaner or
instance adapter is required. Expected: normal `go test` passes; `go test -race`
reports conflicting memory accesses. This does not by itself settle whether the
underlying WASM operation is permitted, or whether Go race instrumentation is an
adequate model. It must not be used to justify suppressing reports.

Copy to a disposable nested module as `precheck_test.go`, using module name
`github.com/masahitojp/mariamem/diagnostics/precheck`, requiring mariamem v0.0.0
with an explicit development replacement of the checkout. Run with Go1.26.8.
Use `GORACE=halt_on_error=1 go test -race -count=1 .` to retain only the first
report. The failing diagnostic is intentionally outside normal package discovery.
No generated source is edited. See the production direct-link baseline report.

The [origin investigation](../../direct-link-futex-race-origin.md) traces the
ordinary read to the pinned libc and guest `i32.load`, with the competing
`i32.atomic.rmw.cmpxchg`. `race-instructions.go.txt` is a decoder template:
copy it to `cmd/raceinspect/main.go` in a disposable checkout of the pinned
wasm2go fork (it imports that fork's internal parser), then run:

```sh
GOTOOLCHAIN=go1.26.8 go run ./cmd/raceinspect /path/to/canonical/guest.wasm
```

It prints imported function indexes and complete instruction bytes for functions
88/219. These indexes are diagnostic evidence for this checksummed artifact,
not a production function-index workaround. Body offsets include local declarations.

To repeat the source/IR probes, extract the locked WASIX libc source archive's
`libc-bottom-half/sources/__wasilibc_futex.c` unchanged. Separately extract
`libc-top-half/musl/arch/wasm32/atomic_arch.h` and compile this wrapper:

```c
#include "atomic_arch.h"
int probe_cas(volatile int *p, int expected, int replacement) {
    return a_cas(p, expected, replacement);
}
```

Use the pinned reproducibility build image and LLVM prefix from
`docs/v04-guest-reproducibility.md`, with `WASIXCC_WASM_EXCEPTIONS=legacy` and
`WASIXCC_RUN_WASM_OPT=no`; run `wasixcc -O2 -matomics -mbulk-memory -pthread
-S -emit-llvm` on each input. The first produces volatile non-atomic loads,
the second sequentially consistent cmpxchg. No guest regeneration or manual
generated-source edit is required for this investigation.
