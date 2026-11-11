# UCA startup source attribution — pinned source notes

Pinned upstream: MariaDB commit `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`.
The four downloaded source hashes and commit-tree identity are in `uca-source.json`.

- `include/m_ctype.h:856–876` defines `CHARSET_INFO`: number first, followed by
  primary/binary/state and two LEX_CSTRING pairs. In WASM32 the observed number
  is at offset0 and collation name pointer/length at24/28. These read-only loads
  are bound to this guest and not a public structure decoder.
- `mysys/charset.c:862–924` resolves a descriptor, serializes lazy initialization,
  invokes charset/collation initialization and then sets MY_CS_READY. Ready state,
  locks, statistics, handlers and ownership remain guest-local.
- `strings/ctype-uca.c:34582–34590` sets pad/ctype/casefold and creates tailoring.
  `create_tailoring` at34737 parses rules, chooses UCA version, and either shares
  an initialized per-encoding/per-tailoring object within this guest or allocates
  another object. It does not share a running MariaDB across Forks.
- `my_uca_info_init` at34675 copies source metadata, clears only its destination
  levels, then initializes selected levels. `init_weight_level` at34460–34575
  validates rules, allocates/copies page-length and pointer arrays, generates
  tailored pages, allocates/copies/applies contractions, populates their hash and
  conditionally builds a booster. Thus its observed time includes all those
  branches; a weight-level timer alone is NOT proof any single branch dominates.
- `my_uca_level_booster_populate` at34264 traverses one/two-byte mappings and
  contractions plus a65536-entry weight2 loop. The canonical patch already
  bypasses population for exact default PAD ai_ci IDs2048/2304 and levels0–2,
  retaining private equivalence verification and fallback for all other IDs.
- UCA1400 `my_uca1400_collation_get_initialized_shared_uca` at34698–34716
  initializes all three levels once per encoding/tailoring within a guest.

This experiment adds function-entry/exit callbacks only. It does not remove a
collation, change SQL defaults, bypass contraction rules or share mutable state.
Function-map and full-file/body hashes are retained. Host elapsed time includes
observer and scheduling cost; it is not exclusive CPU. Nested times must not be
added to their parents. Detailed contraction/page/tailoring subphase timing is
not supplied by this observer; a later candidate must justify any such attribution.
