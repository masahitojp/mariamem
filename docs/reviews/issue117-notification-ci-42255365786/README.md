# Disconnect notification accepted on main

PR118 merged to main `2434a536c50e5bd23129dd9940d6371e80a23366` after
Development42254980323 and both-platform candidate42255365786 succeeded at
`a5fce7485cb4cb74cbc982c8c342a104f06c8ca6`. The candidate and squash commit
have identical tree `0fa6676b8bcbf3256df8b5dd00e3e16058f2ed51`.

Both macOS15 arm64 and Ubuntu24.04 x86_64 pass focused notification/worker/disposal
contracts with handwritten race instrumentation, real TCP/Pipe retirement,
Snapshot/cap1 child reuse and the bounded connection-retirement benchmark.
Generated engine code is excluded from race instrumentation. These are candidate
acceptance results, not release qualification or a full-suite performance result.

assessment.json records artifact IDs and API ZIP SHA256 values. Downloaded ZIP
bytes and every original member hash were checked before selecting this compact
set. The saved measurement.json retains all six numeric pairs; per-process
benchmark console logs and the duplicate generation ledger are not retained here.
The source, toolchain, platform, binary hash and contract/runtime outputs remain.
Local SHA256SUMS.json authenticates the saved subset.

The benchmark measures pool.Close + WaitDisconnected on one reusable Pipe DB;
SQL/setup/final Database.Close are excluded. It is not a Fork, full cleanup,
CPU, memory or whole-batch comparison. No timing threshold or excluded pair.

[Candidate CI](https://github.com/masahitojp/mariamem/actions/runs/42255365786)
· [Development](https://github.com/masahitojp/mariamem/actions/runs/42254980323)
· [PR118](https://github.com/masahitojp/mariamem/pull/118)
