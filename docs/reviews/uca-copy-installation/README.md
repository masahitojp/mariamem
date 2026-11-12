# Canonical UCA private-copy installation

The source checkpoint owns status: [canonical candidate](../uca-copy-canonical.md).
The installed guest is332e0108… from canonical-source bootstrap43185761193 at
c4c60edaf7c6c9bd51023f352be696033e17438d. It is the exact accepted experimental
guest, but its source and receipt remain independently recorded. Single-build
origin is UNQUALIFIED; no old runtime/platform result is relabeled.

The pinned converter and all existing adapters reproduce the source. Only the
worker complete-body hashes and CRC complete-body/table address are rebound.
[Binding comparison](binding.json) records full preimage hashes and integer
deltas: worker address shifts749632; CRC shifts749632 plus one previously
reviewed diagnostic string move34. No approximate runtime matcher or extra
accepted guest is added. Allocation handoff, CRC calculation/comparison and
failure handling remain the same. The CRC corruption fixture moves only its
table/page-size setup addresses; its differential assertions are unchanged.

The normal15-profile UCA test checks original/private-copy payload equality,
corruption rejection, ordinary/profiling verification separation and mapping
cleanup. The native SQL owner adds five encodings, alias/query order and two
independent children. reSnapshot preserves collation rows and the parent.
These are promoted bounded tests, not broader lazy-init/OOM coverage claims.

Local installation verification and151 focused Python tests/15 subtests pass.
The fixed Binaryen133 Mac archive reproduces the exact guest from linked.wasm
while generating its function-name map. Clean-source host attribution and actual
runtime checks are pending at this checkpoint. No performance run is added.

Reproduce via the existing pinned translate_guest.py and setup_candidate.py
--source-only, then scripts/generate_runtime.py with current canonical input
pins. scripts/regenerate_release_guest.py repeats the full translation, memory32
fixture, adaptation, installation and complete-file comparison in each CI host.
The source tools reject drift before execution. Dedicated temp/cache/downloads
are removed after recording compact proofs. Generated source in the PR is
product code; it is not retained measurement output.
