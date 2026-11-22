# Experimental B1 native wire glue (Issue #238)

Self-owned native wire glue files for MariaDB 12.3.4 on branch
`experiment/native-wire-contract` (not release-eligible; canonical
`guest/source.patch` and `guest/input.json` are unchanged).

| Destination in prepared tree | Source in repo | Purpose |
| --- | --- | --- |
| `libmysqld/mariamem_control_abi.h` | `guest/native/libmysqld/mariamem_control_abi.h` | C ABI between MariaDB session callbacks and `issue65_control.cc` |
| `libmysqld/mariamem_wire_probe.inc` | `guest/native/libmysqld/mariamem_wire_probe.inc` | Memory `Vio`, native `THD` lifecycle, `--max-allowed-packet` wiring into `thd->net.max_packet_size`, lifecycle hooks (`dispatch_start`, `rollback_result`) |
| `wasm/issue65_control.cc` | `guest/native/wasm/issue65_control.cc` | Native transport/session frame manager (`DATA` never parses MySQL wire bytes) |
| `wasm/issue65_deadline.h` | `guest/native/wasm/issue65_deadline.h` | Monotonic steady-clock deadline helper |

Intentionally omitted compared to `a6ccc071`:
- `sql/mariamem_wire_policy.h` (removed under the Issue #238 native-contract switch;
  command allowlist, handshake rejection, and output packet cap are retired in favor
  of native MariaDB 12.3.4 behavior and server settings).

`scripts/prepare_guest.py` verifies each file's SHA-256 against `manifest.json`,
rejects pre-existing destinations or symlinks, installs with mode `0644`, and
records the exact hashes in `prepared-source.json`.
