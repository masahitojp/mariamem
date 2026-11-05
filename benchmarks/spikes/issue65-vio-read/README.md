# Issue65 — native NET read/framing over memory Vio

**Step1 only: PASS in the isolated source-extraction fixture.** The pinned
upstream uncompressed reader works over memory callbacks, including large-message
reassembly and the specified malformed/truncated-input controls. This completes
the requested read-side seam experiment. It does not prove a complete embedded
packet endpoint, native server acceptance profile, handshake, SQL or prepared
execution. Retain the I/O-shim approach as a plausible How within option1; decide
the next hybrid/prepared experiment separately.

## Fixed scope and reproducible inputs

- MariaDB12.3.3 source_commit: `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`.
- Harness starting source_commit: `400dc3325f1a9992cbe1e4596e9ffa770e272ca5`.
  The read harness is the experiment diff, not a tested product runtime.
- Product reference: `47121e1be0b399ba4e2270ce3e25c411ade0e2eb`.
- Inputs: `include/violite.h`, `include/mysql_com.h`, `sql/net_serv.cc` with
  exact SHA256 checks. Source bodies are extracted unchanged for `net_realloc`,
  `handle_proxy_header`, `my_real_read`, `my_net_read_packet_reallen`,
  `my_net_read_packet` and `my_net_read`.
- Support/extraction comes from the earlier [writer probe](../issue65-vio-smoke/README.md).
  The receipt binds both harness files, generated source and each extracted body.
- Existing Linux/arm64 image
  `sha256:3ded805d8dcae3ffdf39515c3f0540b27b695719570903594452f8787abe570f`,
  GCC13.3.0. No OS socket, listener or network access in the test container.
- C++17, `-Wall -Wextra -Werror -Wno-unused-parameter -O1`, ASan/UBSan.
  `ASAN_OPTIONS=quarantine_size_mb=16:detect_leaks=1`,
  `UBSAN_OPTIONS=halt_on_error=1`. Quarantine size bounds diagnostic memory;
  no sanitizer errors are suppressed.
- CPU1, memory512MiB, compile30s/run20s/outer90s timeouts,
  disposable1GiB and minimum free8GiB. No server/guest build, SQL, prepared
  experiment, benchmark or CI submission.

## Actual profile and fixture boundary

`EMBEDDED_LIBRARY` is defined and `MYSQL_SERVER` is unset, matching the selection
made near the top of net_serv.cc for embedded builds. Compression is compiled out,
`pkt_nr_can_be_reset=0`, `retry_count=0`, timeout callback false and NET extension
null. The fixture performs buffer initialization; my_net_init and Vio allocation
are not tested. A minimal declaration supplies the unused instrumentation callback
shape; platform typedefs, allocator and no-op diagnostic hooks are fixture support.
This is not a complete upstream-header/library build, ABI test or actual THD.

Only the temporary large-message fixtures raise max_packet_size. The product's
SQL/input cap and unsupported packet-continuation declaration are unchanged.
Noncompressed continuation uses `where_b`; `remain_in_buf` belongs to the
untested compressed path.

## Observations — all15 groups PASS

| Group | Confirmed observation |
| --- | --- |
| Header/body fragmentation | Exact reconstruction with callback chunks1,2 and5; trailing safety NUL present |
| Two consecutive frames | Independent payloads, including embedded NUL, decoded in order without losing the next header |
| Wrong sequence | Sequence2 while expecting0 returns packet_error before reading payload; reset remains disabled |
| Sequence wrap |255 then0 accepted, internal sequence advances to257 |
| Previous-sequence non-ERR | Previous number with ordinary payload is rejected |
| Previous-sequence ERR | Existing client-side exception accepts a previous-number payload beginning0xff; observed rather than hidden |
| Empty packet | Returns length0 with the expected safety terminator |
| EOF during header | Returns packet_error/error2/ER_NET_READ_ERROR and clears reading state |
| EOF during payload | Same failure controls, no fabricated complete message |
| Buffer growth |65,535-byte payload triggers the original reallocator and retains data |
| Limit after growth | With max_packet_size65,536, a subsequent65,536-byte request is rejected with ER_NET_PACKET_TOO_LARGE |
| Over-limit header |65,537-byte advertised payload is rejected after its header with the same configured limit |
| Multi-packet continuation |0xffffff bytes plus7-byte tail become one exact payload; where_b is restored and sequence advances |
| Exact0xffffff boundary | Full-length packet followed by an empty terminator returns exactly0xffffff bytes |
| Missing terminator | Full-length packet followed by EOF fails and restores where_b |

One native run passed all assertions with no ASan/UBSan/leak diagnostics.
The three fragmentation chunk sizes are one reported group, not three independent
platforms/runs. Large successful payloads are checked across every byte, not just
length/endpoints. Frames are constructed by the test fixture, not the previously
tested upstream writer, to avoid requiring two matching framing bugs.
[Raw execution](evidence/run.txt), [source-bound receipt](evidence/result.json),
[environment](evidence/environment.json).

## Important interpretation limits

The profile's client-side previous-sequence ERR exception is in the upstream
my_real_read conditional branch; disabling pkt_nr reset does not remove it.
Therefore the PASS is not a claim that all sequence mismatches are rejected,
or that the normal MYSQL_SERVER profile has been tested. The future command-path
build must deliberately choose and verify its profile rather than assuming the
embedded NET selection is identical to native server command reception.

The allocation guard rejects `length >= max_packet_size` at net_realloc; tested
bounds were chosen around buffer-growth boundaries and this exact behavior is
recorded. This is not a proof that max_packet_size alone enforces a universal
per-command budget under every buffer/state configuration. Product input limits
are a separate existing boundary and were not changed or requalified.

Unverified: compression, asynchronous/timeout/retry/kill callbacks, real NET/Vio
initialization, proxy protocol and instrumentation, production denial-of-service
bounds, concurrent lifetime/worker joining, server command decoder, native
handshake, embedded/native prepared input and response metadata, bootstrap,
Snapshot/Fork/Live and WASIX/Go callback generation. No throughput/latency claim.
The next material question remains the coherent prepared-input boundary; it
cannot be resolved by more repetitions of this memory-framing fixture.

## Reproduce and cleanup

Fetch the three pinned files retaining their relative paths and verify the
script's hashes. From the experiment checkout on a native Linux GCC toolchain:

```sh
python3 benchmarks/spikes/issue65-vio-read/run.py \
  --source /path/to/pinned-source --output /fresh/disposable/output
```

Use the recorded sanitizer environment and existing experiment disk guard.
No full verify.py/runtime/ORM/Release acceptance is warranted by this standalone
fixture. Python syntax, evidence consistency, public-source boundary and diff
checks accompany the actual native run. Original user changes remain untouched.
Compact reports/scripts/receipts are retained in the experiment branch; owned
source copies, compile output, container and worktree are removed after completion.
