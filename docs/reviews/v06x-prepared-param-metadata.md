# P4 LONG_DATA CI failure: engine-owned PREPARE metadata repair candidate

## Confirmed failure, not LONG_DATA acceptance

[CI39718930329](https://github.com/masahitojp/mariamem/actions/runs/39718930329)
failed on both supported OSes at source_commit
`e5f77f035ff304b4fe5fbd10e54f717090331045`.
Guest-source and both unit jobs PASS. On both OSes formal generation/compilation,
SQL/transaction/Snapshot/Fork/Close smoke, exact installed binding/19 mutations,
P1/all72 P2, minimal/full14 P3 and first7 P4 lifetime cases PASS.
LONG_DATA25 individual assertions PASS, but strict native comparison FAIL:
24 cases differ, with91 parameter descriptor name occurrences per OS.
This is a real metadata mismatch, not a flaky job or proof of runtime acceptance.

The [failure analysis](v06x-prepared-param-metadata-evidence/failure-analysis.json)
checks every compared field of all25 cases. Only the parameter's name differs:
for `SELECT ? AS a`, native PREPARE names the parameter `a`, while the candidate
sends `?`. Every other descriptor attribute, result descriptor/row, error trace,
stream recipe and following-query assertion matches the fixed native control.
Both original failed JSONs and logs are saved beside the analysis. The prior P1
control's unaliased placeholders and cast expressions did not expose this gap.

User consequence: driver metadata is inaccurate for aliased parameter expressions.
These tests did not reproduce wrong SQL values or transaction results. The strict
oracle correctly blocks acceptance; it is not removed or normalized to ignore names.

## Source cause and bounded repair

Fixed upstream MariaDB83e909fc's network `send_prep_stmt` serializes
`stmt->lex->param_list` through the text protocol with forced column metadata.
The embedded version records only counts; `mysql_stmt_param_metadata` is a stub.
The original host bridge therefore emitted a constant `?` descriptor. That
observed equivalence was too narrow. Source references:

- [sql/sql_prepare.cc](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/sql_prepare.cc#L433)
- [libmysqld/libmysql.c](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/libmysql.c#L1879)
- [libmysqld/lib_sql.cc](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/lib_sql.cc#L1105)
- [sql/protocol.cc](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/protocol.cc#L1320)
- [mysql_free_result ownership](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql-common/client.c#L749)

The repair is an experimental guest extension, not host SQL parsing:

1. WASIX embedded-only `mysql_stmt_param_metadata` obtains the owning prepared
   statement's parser-owned parameter list. It synchronously invokes the existing
   embedded `Protocol_text::store_item_metadata` conversion for every descriptor,
   retaining engine-derived names, types, flags, charset and lengths. The list
   view is the same Item_param-to-Item view used by native send_prep_stmt; it
   remains coupled to this exact upstream source identity.
2. A private temporary MYSQL_DATA points at an independent MEM_ROOT and field
   array. It never enters the result queue or executes SQL. Current THD/data context is restored after conversion. Worker stack/mysys/kill
   state is left unchanged: metadata formatting does not call store/reset_globals. The returned MYSQL_RES owns its
   copied fields until `mysql_free_result`; no parameter binding or engine pointer
   crosses the guest/host envelope. Allocation failures free the private root.
   The existing string-allocation conversion gets a WASIX null check before
   strlen; the wrapper also rejects a missing catalog instead of dereferencing it.
3. The authored C bridge serializes parameter columns into the internal PREPARE
   envelope and frees both parameter/result metadata on every ownership path.
   Missing metadata or mismatched count fails closed; no generic-name fallback.
4. Go requires exactly ParamCount descriptors before exposing a wire handle and
   serializes each independently. The constant descriptor is now test-only.
   LONG_DATA acknowledgements reject unexpected parameter metadata too.

The fixed experimental patch now owns exactly three complete source files:
`sql/sql_prepare.cc`, `libmysqld/libmysql.c`, `libmysqld/lib_sql.cc`.
Their pre/postimages and patch digest are in guest/prepared_source_patch.json.
Application checks all three preimages before mutation, zero-fuzz patch success,
all postimages and the existing P2/parameter-order complete-function fixtures.
The initial TIME patch and all earlier repairs remain. New code is WASIX
embedded-only; canonical source.patch and converter13 patches stay unchanged.

This adds upstream maintenance surface: retain the three exact pre/postimages
and re-review the parameter-list lookup, protocol conversion and result ownership
when rebasing MariaDB. Do not carry the extension forward by updating hashes alone.
Canonical adoption remains P6 work and needs independent regeneration/J1 closure.
The guest changes necessarily require a new source build and exact binding review;
the current f5ce001d owner deliberately rejects that still-unknown guest.

## Verification and next gate

The C mock tests exercise parameter metadata copying through the real authored
bridge, missing/count-mismatched metadata, entry allocation/serialization failure,
statement cleanup and both normal/ASan/UBSan builds. They do not prove embedded
C++ semantics. Go tests check per-parameter alias forwarding and missing/excess
array rejection. A mutation control preserves the observed `a`→`?` mismatch as
an unconditional failure of the unchanged native comparator.

The actual fixed-source three-file patch applies with zero fuzz and matches
all pinned postimages locally. Existing source-function proofs remain in place.
The unchanged canonical inventory check concerns the old canonical guest only.
Detailed local results and hashes are in the evidence receipt. Full embedded
C++ compilation/new guest execution are **PENDING source CI**, not local PASS.

Push the exact candidate to `experiment/prepared-param-metadata`: source builder
and both OS units run, development-runtime SKIPs intentionally while the old
single-guest binding rejects unknown inputs. After source success, verify the
clean-source artifact inventory, translate with unchanged fixed converter13
patches, review complete function/data/TLS/init preimages, then submit the newly
bound candidate on prepared-product for the full both-OS runtime matrix.
No expected native packets, LONG_DATA cases or prior gates are removed.

No main integration, version placement, Qualification or release. LONG_DATA
acceptance, the remainder of P4 and P5/P6 stay unfinished.

## Source compilation and binding follow-up

Source CI39724676227 passes guest-source and both OS unit jobs at ab8c350.
The [exact binding evidence](v06x-prepared-param-metadata-binding/reproduce.md)
now binds guest8f617762 to fixed converter13 patches and reviewed BSS+64
function/init changes. Local122 focused checks, formal source-only adapter and
pure owner transforms PASS. The source compilation concern above is resolved;
actual strict runtime/native metadata parity remains PENDING.

## Both-OS LONG_DATA/native metadata development gate closed

[CI39729456821 at fba09f6](v06x-prepared-long-data-pass.md) passes all25
LONG_DATA/native comparisons including the previously wrong parameter names,
plus the previous runtime gates and cleanup controls on both OSes. No oracle
or native fixture was weakened. Full P4 (active-query cancellation/disconnect
and remaining failure/resource paths), P5/P6 and adoption remain unfinished.
