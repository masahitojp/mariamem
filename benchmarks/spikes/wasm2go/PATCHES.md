# Production upstream patch series (v0.4.7 candidate)

Base: goccy/wasm2go `730057c146463f663e8774587bc96fb2bea91af8`.
Archive and output identities are pinned by `release/generated-go-{toolchain,translation,inputs}.json`.
The canonical runner is `../generated-go-integration/translate_guest.py`.

Order | Patch | Responsibility
--- | --- | ---
1 | imported-memory.patch | Populate imported memory metadata before translation (upstream context port)
2 | import-function-index.patch | Preserve imported function indices
3 | relaxed-madd.patch | Existing relaxed SIMD multiply-add handling
4 | pure-memory32.patch | Effective address, logical bounds, alignment, trapping-load SSA (upstream helper context port)
5 | controlled-thread-traps.patch | Capture worker panics and cooperatively join
6 | host-logical-memory.patch | Host-import buffers see logical memory only
7 | linear-memory-owner.patch | Existing external backing and grow ownership contract
8 | helper-bridge.patch | Logical memBound and Wait fixture contention capability
9 | export-collision.patch | Preserve both exports using the established suffix rule

Five patches are byte-identical to v0.4.6; 1/4 are context ports; 8/9 preserve required
fork capabilities. Track A evidence is on `experiment/v05-wasm2go-upstream-feasibility`
(`9a130274bff87d4a814cc1cac6c6cb6c1cc62a5f`). No optional fork layout or experimental
Go1.27 SIMD route is adopted. Generated call-site/address patches are not used.

Patch application is not runtime qualification. Preserve memory32/reference,
thread/TLS/futex, ownership, real guest, consumer and independent regeneration gates.
Zero-length bulk-memory bounds and general generated shared-memory race limitations
predate this migration; this series does not claim to resolve them.
