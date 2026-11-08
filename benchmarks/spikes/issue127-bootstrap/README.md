# Issue127 — bounded bootstrap separation

Question: can the native guest preserve embedded text bootstrap while excluding
legacy resident/prepared entry and exported JSON roots, lowering the surface to
repair on a MariaDB update? Base source_commit:
`a5ee1ed9cc2c6932d317fba77c339b364acd48df`, verified with
`scripts/git_identity.py inspect HEAD` and the local
`experiment/issue65-bootstrap-reachability` ref before edits.

Budget recorded before investigation/build: active 2h, measurement tooling 30min
within that, heavy CI 0; one candidate and at most one heavy guest build.
Environment: macOS arm64, Python /opt/homebrew/bin/python3.14; canonical guest
builder requires fresh root Linux arm64. Free-space floor 12GiB, owned scratch
ceiling 12GiB; stop before building if either cannot hold. Build timeout 60min
within the remaining active budget; source preparation timeout 15min.
All owned outputs stay under this checkout's build/issue127 or build source/
downloads/unpack paths and are removed after reducing evidence. No shared cache
or other worker outputs are owned. Orca checkout lifecycle belongs to coordinator.

Finite evidence: reconstruct actual prepared includes/export roots, implement
one isolated entry candidate in experimental.patch, compare canonical inputs,
check source and feasible compilation, then (only if a new guest is available)
compare symbols/generated bindings and fresh/restore, routines, text/prepared,
and stop using existing oracles. Native decoder, capture gate, ownership,
canonical source.patch and prepared patch remain fixed.

Exit: recommend continue/reject from measured reachable surface and costs.
If builder/runtime cannot finish within budget, preserve candidate, failures,
exact missing evidence and reproduction cost; report inconclusive runtime and
no update-cost benefit established. No main integration/release or parent issue
edit is authorized. The actual version-update comparison remains Issue128.

Candidate: select `MARIAMEM_BOOTSTRAP_ONLY` for the existing glue translation
unit; keep the exact l4m_open/l4m_close and issue65_bootstrap/shutdown bodies,
exclude JSON helpers and wire_api (therefore prepared_api/resident/snapshot_fs),
and include only auth/routine bootstrap. Remove seven l4m export roots and dead
controller embedded-prepared examples plus their mysql/routine includes.
No duplicated bootstrap implementation and no engine patch removal.

Pre-build source check passes: complete open/close/bootstrap and Manager bodies
are unchanged; canonical patch/prepared patch/input/preparation script hashes are
fixed. Existing Docker image is Linux aarch64 but contains LLVM21.1.2, so it is
only an OS carrier; the canonical builder installs the locked LLVM23 and SDK
under a fresh owned bind mount. The build uses an empty owned /work, read-only
source, fresh owned SDK, canonical build_generated_guest.py development route,
and its unchanged clean-source/toolchain guards. Prepared sources are checked
again before compile. Output is UNQUALIFIED, never release evidence.
