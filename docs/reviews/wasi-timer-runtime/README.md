# WASI timer: bound development runtime oracle

This is the follow-on to the successful unqualified guest build
[CI42916730601](https://github.com/masahitojp/mariamem/actions/runs/42916730601)
at source_commit `9a3e91b708cc765b418b77ddc7278e2151f2cf5c`.
The new guest SHA256 is
`b68fce3a4785f5a9dd858c96572ed0a765ee4352715b416cdf168784054b4fc6`.
No adoption, canonical guest change, calibration omission or release is implied.

## Binding inspection before execution

`binding.json` records the new data/guest identities and exact comparison:
all three ownership/reclaimer functions have unchanged whitespace-normalized
complete-body hashes; the complete CRC validator is byte-identical, and its
4096-byte table and offset are identical. No function-number/address relocation
or semantic normalization was necessary. The development-only selector changes
only the two guest identity constants after checking those unchanged identities.
The canonical installation route never invokes it. Full inventory, source origin,
patch, data, table, function-body and transform checks remain mandatory.
The focused tests reject data/CRC/thread-binding drift and unknown guests.

## Fixed scope and reproduction

Budget: one host build, 120 minutes, 16GiB owned and 8GiB free reserve. The initial
inspection translation is repeated by the existing guarded development installer.
Use Python3.14, pytest9.1.1, PyMySQL1.2.0 and Go1.26.10 in an owned workspace.
The first translation attempt used system Python3.9, which lacks tarfile's data
filter; it stopped before conversion. A conflicting inherited GOPATH was also
rejected before converter acquisition. These are local setup attempts, not guest
or runtime failures. They did not change tool/source pins or extraction guards.

1. Fetch both CI artifacts; check the archive digests in the receipt. Extract
   into owned scratch. `scripts/dev_guest.py:verify_guest` verifies the original
   clean source and every guest/tool/patch binding.
2. Use the locked converter archive with
   `benchmarks/spikes/generated-go-integration/translate_guest.py`, then
   `setup_candidate.py --source-only`. `verify_translation` checks the result.
3. Run `tests/timer_runtime/inspect_binding.py --candidate-module MODULE
   --guest GUEST --output EVIDENCE`; compare its provisional record with the
   committed binding. It reports drift; it never installs a permissive binding.
4. On this clean committed source run
   `python scripts/regenerate_release_guest.py --development --guest-dir GUEST
   --output OWNED_EXTERNAL_OUTPUT`. This rebuilds a disposable host and runs the
   existing real SQL/transaction/Snapshot/three-child/cleanup smoke.
5. With the disposable product's `python/` on PYTHONPATH, run
   `python tests/timer_runtime/oracle.py --host HOST --output RESULT.json`.
   Fresh and two sequential Forks each run three ordinary/delayed query pairs.
   The delayed query sleeps10ms on each of two rows: require reported query-block
   total at least18ms and at most client wall+5ms. Verify rows, following SELECT,
   first-child mutation absent in second child, host exit0, closed pipes/thread,
   zero Session refs and removal of the owned Session directory.

The SQL matches the earlier Go Pipe probe, but this oracle uses PyMySQL/TCP.
It establishes SQL reporting correctness, not a transport latency or speedup
comparison. It is single-Mac evidence. Native SQL comparison and both-platform
acceptance are separate; global calibration remains unchanged. The fallback is
upstream gettimeofday, not a new monotonic-clock contract.

Runtime result is pending the bound host execution; do not read the guest build
or binding comparison as actual ANALYZE PASS.
