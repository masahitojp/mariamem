# TIME guest binding reproduction

Use source_commit `4f41be87ac30c86cf688b150afb5493fed6b6a1b` and inspect it with
scripts/git_identity.py. Download the matching unqualified guest artifact from
[39572844101](https://github.com/masahitojp/mariamem/actions/runs/39572844101).
Verify its full source inventory, preparation/experimental patch, toolchain,
Wasm and linked-Wasm identities with dev_guest.verify_guest in that clean source.
receipt.json records the source and artifact hashes. Do not expand cross-commit
source-origin acceptance to bypass the changed binding script.

With Python3.14 and actual pinned Go1.26.8, use the exact converter commit/archive
and13 patches in translation-inputs.json. Run translate_guest.py with explicit
--guest, --guest-sha256, --converter-archive and fresh --output. Verify complete
raw inventory with dev_guest.verify_translation. Run setup_candidate.py
--source-only with that raw module/input-manifest and guest. All work is isolated
under an experiment workspace (24GiB budget,8GiB free floor). Strip inherited
GOPATH/GOCACHE/GOMODCACHE when selecting workspace-local caches.

binding-review.json records complete function-body hash/fixture comparisons and
full data/TLS identity. raw-inventory-comparison.json compares every raw output
hash with the previous P2 translation, without treating matching inventory as
proof of all runtime semantics. Use formal adapter output before atomic/MemFS/
lifetime owner transformations; the raw base is not the MemFS pinned preimage.
These pure transform checks do not execute a guest or complete full installation.
The505-byte TLS and memory-init declarations are covered by unchanged full data
and generated.go hashes. Function preimages are reused byte-for-byte; only the
single guest SHA in the binding and its identity fixture changes.

Run the five suites listed in local-tests.txt. The full prepared-product CI
rebuilds the source at the submitted commit, performs formal development
installation/compile/smoke, exact installed checker and failure mutations, then
actual P1, original P2 and extra TIME/native comparisons. Those comparisons are
pending at submission. Independent source reproduction and full J1 controls
remain P6; neither source preflight nor this local translation substitutes for them.

The first helper run used a relative script path from its worktree, failed before
translation and was cleaned. The absolute-path retry used identical fixed inputs.
Existing SSA fixpoint/f16 diagnostics are retained; no converter change suppressed
them. Logs replace only local absolute paths, with original/stored SHA recorded.
cleanup-source-proof.json verifies extracted converter source can be recreated
exactly from the pinned archive/patches before removing its disposable Git
metadata and build scratch. No generated Go edits, main merge or publication.
