# Timer canonical candidate receipt

[Run42959675387](https://github.com/masahitojp/mariamem/actions/runs/42959675387)
passed at `370231520c373fae05378bddb791c9b6d7fdf84f`.
All five artifact ZIPs were authenticated against GitHub's SHA256 digest.
Both native artifacts' file checksums were verified; `verify_build` was replayed
against the committed118-file runtime inventory, exact pins and downloaded
canonical guest. The source includes the approved timer changes and normal
regression owners; it contains no experimental overlay.

| Gate | macOS15 arm64 | Ubuntu24.04 x86_64 |
| --- | --- | --- |
| Independent full Go regeneration / canonical guard | PASS | PASS |
| Timer source controls / TCP+Pipe Fresh and two children | PASS | PASS |
| CRC / actual UCA+lexer / worker isolation | PASS | PASS |
|20 evidence mutations rejected | PASS | PASS |
| J1:2 expected failures +4 protected cases | PASS | PASS |
| Native SQL differential /2 pristine children / cleanup | PASS | PASS |

The source builder independently produced the same guest twice. Native MariaDB
12.3.3 reference is the existing normal/binary-prepared SQL oracle, not a new
native timing or performance comparison. SQL timer oracles use client wall-time
bounds on both guest platforms. The prior single-build bootstrap retains its
original UNQUALIFIED identity and is not relabeled.

`assessment.json` binds source, jobs, artifacts, guest and host hashes;
`artifact-file-sha256.json` inventories all original artifact files. Small test
outputs and JSON results are retained with `SHA256SUMS.json`. Full compiler logs,
WASM and duplicate regeneration inventories remain disposable CI artifacts.

These receipts establish bounded candidate correctness, not Qualification,
release approval or a whole-suite speedup. Main integration needs its own Human
review. Follow-up edits only record evidence and acceptance metadata; guest
patch, generator, runtime bytes and test implementation remain unchanged from
37023152. No runtime rerun is inferred at the later record commit.
