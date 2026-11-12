# UCA canonical candidate receipt

[CI43190662084](https://github.com/masahitojp/mariamem/actions/runs/43190662084)
passed at `6da771df36fb452b920a3ae42e778ce110e46213`.
Two independent canonical C builds produced identical guest and linked hashes.
Both macOS15 arm64 and Ubuntu24.04 x86_64 passed independent Go regeneration,
canonical build guards, CRC/UCA/lexer/worker controls, timer TCP/Pipe controls,
native SQL comparisons, two pristine children, Snapshot/reSnapshot and cleanup.
All five artifact ZIP digests and both platform file-checksum manifests were
verified. The canonical build guard was replayed against the original test source.

`assessment.json` retains source, jobs, artifact digests and bounded outcomes;
`artifact-file-sha256.json` retains original file identities. Raw logs, REST
responses, native row payloads, regenerated inventories and WASM stay outside
Git. `SHA256SUMS.json` covers this compact receipt. This is correctness evidence,
not new performance evidence, main integration, Qualification or publication.

## Separate Development failure and test correction

[Development CI43190666216](https://github.com/masahitojp/mariamem/actions/runs/43190666216)
failed `TestPageOnlyRangeCompleteness`. Its negative control removed the page at
the former init flag address 26996016. Generated `p7.Fn67` now initializes the flag
at 27745648, after the 749632-byte UCA data relocation. The stale address no longer
selected an initialized page; the test mutation became a no-op. Integration and
Live required gate then failed because source checks failed, not independent
runtime failures.

The follow-up changes only `internal/generatedgo/image/image_test.go`, records
and build-acceptance metadata. It relocates the sampled data/TLS/BSS/flag addresses,
asserts the actual flag equals 2 beyond DataEnd, and asserts that the negative
control really removes its page. Complete initial-memory equality, child isolation,
missing-page detection and zero final mapping ownership remain required.

Local Go 1.26.10 macOS checks pass for the complete image and imagelayout packages.
Restoring the old flag address is rejected by the new explicit fixture precondition.
Generated-source/input verification also passes, along with 72 focused Python
tests and 10 subtests for inventory, distribution/license mirrors and UCA source
controls. Production runtime, guest source,
generated implementation and workflow bytes are unchanged from 6da771df; reuse
of the canonical receipt is on that basis. The changed test is not claimed to have
run in the earlier CI. New Development checks must pass before protected merge.
