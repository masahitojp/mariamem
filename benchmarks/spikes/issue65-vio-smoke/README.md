# Issue65 — ultra-light NET/Vio send seam probe

**Result: the isolated native packet writer can send through a memory-backed Vio.**
This supports using Vio as the byte-transport shim boundary. It does not establish
that native protocol and embedded sessions can be combined, or that host wire
code can already be removed. Option4 remains a How within option1.

## What ran

Pinned MariaDB12.3.3 source_commit
`83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`; product baseline
`47121e1be0b399ba4e2270ce3e25c411ade0e2eb`.
`run.py` checks all three source hashes and extracts upstream NET/Vio declarations
plus four unchanged functions from `sql/net_serv.cc`: `my_net_write`,
`net_write_buff`, `net_real_write` and `net_flush`. The generated fixture retains
the upstream writer's copyright/license header.

The fixture supplies platform typedefs, a MYSQL_SOCKET placeholder whose fields
are unused by these tested paths, buffer setup, no-op diagnostic/instrumentation
macros, and memory read/write callbacks. Thus this is source extraction in a
small compatibility harness, NOT a complete upstream-header/library build or an
ABI/layout compatibility test. MYSQL_SERVER is unset, compression disabled and
EMBEDDED_LIBRARY defined for this isolated fixture. Native prepared/Protocol/THD
code is not compiled.

Linux/arm64 in existing image
`sha256:3ded805d8dcae3ffdf39515c3f0540b27b695719570903594452f8787abe570f`,
GCC13.3.0, C++17, `-Wall -Wextra -Werror -O1`, ASan and UBSan. Container network
was disabled, CPU capped at1 and memory at256MiB. Compile timeout30s, execution10s,
outer watchdog60s, owned disk1GiB and minimum free8GiB. No image installation,
server/guest build, native SQL, performance measurement or CI submission.

## Observations

| Control | Result |
| --- | --- |
| One payload framed by the upstream NET writer | Exact expected length/sequence/payload bytes |
| Write callback accepts at most2 bytes per call | Native write loop drains the whole packet correctly |
| Memory read callback accepts at most2 bytes per call | Exact byte round-trip and then EOF; this is a fixture read, not my_net_read |
| Empty payload | Native writer emits the expected empty frame |
| Initial packet sequence7 | Frame uses7 and NET advances to8 |
| Write callback returns failure | Flush fails, NET marks error2/errno1160 and clears writing state; no fabricated success bytes |

All assertions pass with no sanitizer diagnostics. The payload contains the bytes
for COM_QUERY/SELECT1 only as a fixed byte string: **no command is decoded and no
SQL is executed**. The expected bytes are an independent fixed test vector.

The initial macOS compiler attempt failed because the C++ standard header
`algorithm` was unavailable. The first Linux compile exposed missing fixture
`uint16`/DBUG_DUMP definitions and a harness indentation warning; only those
fixture issues were repaired. No extracted upstream function body changed.
The macOS log replaces only the personal workspace prefix with `<workspace>`;
its raw hash and normalization are recorded in `evidence/environment.json`.
[Original failure](evidence/macos-compile-failure.txt),
[fixture compile failure](evidence/harness-compile-failure.txt),
[final result/identities](evidence/result.json), [execution](evidence/run.txt).

## Interpretation and next boundary

The concrete positive is narrower than an embedded packet endpoint: the existing
packet writer is not intrinsically tied to an OS socket and can drive memory
callbacks, including partial writes and error propagation. It justifies retaining
the Vio-shim idea; it does not prove the wider architecture or a speed benefit.

Still untested: real Vio allocation/init/fd assumptions, my_net_read/command loop,
handshake/auth, embedded THD initialization, native prepared bindings/metadata,
text/binary Protocol switching, bootstrap coexistence, concurrency, retries,
timeouts/cancellation, worker joining, multi-session limits, Snapshot/Fork/Live,
WASIX/Go generation, compression and large-packet continuation. The next materially
useful experiment would need a coherent embedded/native protocol build. It should
not repeat this shim-only fixture and call it integration acceptance.

## Reproduce

Fetch the three upstream files from the pinned commit into a disposable directory,
retaining paths `sql/net_serv.cc`, `include/violite.h`, `include/mysql_com.h`.
The script rejects different bytes. On a native Linux C++ toolchain:

```sh
python3 benchmarks/spikes/issue65-vio-smoke/run.py \
  --compiler g++ --source /path/to/pinned-source --output /fresh/disposable/output
```

Use the existing experiment disk guard and clean only owned output after preserving
compact results. The final harness/input hashes and binary hash are retained;
no prior failure is rewritten as PASS. The original checkout's four changes stay
untouched. Owned container, upstream copies, compiler output and worktree are
removed after preserving the script/report/results in the experiment branch and
compact evidence. No product code, canonical guest/source patch or release ledger
is changed, and main adoption/release are not part of this probe.
