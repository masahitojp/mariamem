# Issue126: one common-initialization candidate

**Select the compiled-charset lexer maps (`state_map` + `ident_map`) for a bounded
feasibility candidate.** These are two256-byte lookup tables constructed by
`init_state_maps()`. Their contents can plausibly be generated ahead of time;
whole registry/hash objects and live engine state should not be copied. This
source-only result does not establish enough exclusive startup cost to justify
implementation. First refresh the adopted-main lifecycle comparison. If the
map-generation cost is still unknown afterward, a separately bounded call-count/
time diagnostic is needed before an expensive guest prototype, not another
unrestricted common-init campaign.

The strongest objection is that512bytes per map pair may be a small part of
common startup. Even though generation performs classification and indirect
multibyte-handler calls per byte, the number of actual invocations, unique map
pairs and exclusive time on current main are unmeasured. Do not attach the old
7.33ms common interval or3.547ms pre-UCA registry interval to this function.

[Issue126](https://github.com/masahitojp/mariamem/issues/126) follows the completed
#100 UCA attribution and #121 bounded post-UCA investigation. Product baseline
is3d8b2201c1f36fa5b7264e0450104055f3822272; unchanged guest6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe.
MariaDB source83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e was acquired from the
checksum-pinned release input. `source-files.json` records source hashes and
`references.txt` contains the repository-wide explicit field-reference scan.
Canonical guest patches do not change `init_state_maps` or its consumers.
No build/DB run/CI or product edit was made for this feasibility stage.

## Source chain and ownership

All links below pin the same upstream source:

- [charset.c:704–741](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/mysys/charset.c#L704): init_available_charsets resets the registry/statistics, initializes two mutable hashes, calls init_compiled_charsets, then creates missing lexer maps for entries with m_ctype. It subsequently reads Index.xml. The whole registry is not immutable.
- [charset.c:60–119](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/mysys/charset.c#L60): allocate512bytes from my_once_alloc; assign per-CHARSET_INFO pointers; classify256 inputs using m_ctype and my_ci_charlen; apply punctuation rules; generate ident_map; only afterward apply x/b/n prefix rules to state_map. Preserving that order is essential.
- [m_ctype.h:874](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/include/m_ctype.h#L874): both published fields are const-byte pointers. The full-source explicit field scan finds their assignment in init_state_maps and consumers that read them, not post-publication element writers. This scan is evidence, not an alias-analysis proof.
- [sql_lex.cc:2034](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/sql_lex.cc#L2034): the lexer selects the connection charset and reads both maps for token/identifier handling. Additional consumers include simple_tokenizer.h, sql_table.cc, sql_cache.cc and sql_show.cc (scan retained).
- [my_once.c:38](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/mysys/my_once.c#L38): current allocation belongs to the guest's once arena; my_once_free releases blocks, not each map. Static table bytes must never be registered as owned arena blocks.
- [charset.c:143](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/mysys/charset.c#L143) and:386: runtime-loaded/copied character data can also invoke init_state_maps. They must retain the original dynamic route; a numeric collation ID alone is not a sufficient cache identity.
- [charset.c:593](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/mysys/charset.c#L593) and:862: registration mutates CHARSET_INFO/state/hash entries, and lazy charset/collation initialization is protected by THR_LOCK_charset. Per-instance mutable state, statistics, hashes and locks stay per-instance.

## Proposed boundary, not implemented

Generate exact512-byte map pairs for a known compiled charset set from the
pinned classifier/enum/charset definitions. An offline/native producer would
need matching build configuration and full byte equality against the original
algorithm; feasibility of that producer is not yet demonstrated. Deduplication
is optional and only after full byte equality, never based on charset names.

Bind only the compiled-registration route, before Index.xml loading, using the
known descriptor and its classification inputs. Preserve original generation
for unknown/dynamic descriptors. Do not skip charset registration, lookup,
collation initialization or XML handling. Map bytes contain no pointers; the
new field pointers must be assigned to the current guest's static data through
normal compiled relocation. Never reuse another instance's offsets/allocator,
Go pointers, mutexes, TLS or live CHARSET_INFO object. This is guest-side
prepared data (canonical patch/header + normal regeneration if adopted), not
#123 MAP_PRIVATE sharing or #103 whole-state cloning.

A possible later prototype must prove all512bytes equal per admitted compiled
descriptor, input/config drift rejection, original dynamic/failure fallback,
unchanged normal+prepared SQL parsing (Unicode/multibyte identifiers, quotes,
comments, x/b/n prefixes, parameters, SQL modes), native comparison and child
isolation/cleanup. Any removed per-map allocation failure belongs only to the
replaced allocation; do not suppress unrelated errors. Full guest regeneration
and supported-platform acceptance belong to productization, not this read.

## Stop and next action

This bounded source stage is complete: one concrete table pair, producer and
consumer, mutation/ownership boundaries and missing performance evidence are
identified. No full-registry/template prototype is justified. Refresh current
main versus pinned pgmem using the already approved finite lifecycle recipe,
then decide whether the missing exclusive map cost warrants one small diagnostic.
If cost is small or candidate binding proves impractical, defer and return to
#88; do not recursively add more structures. No default/SQL/API/release change
is authorized by this report.
