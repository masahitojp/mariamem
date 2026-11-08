# #137 result: split implemented; combined acceptance incomplete

**Recommendation: retain this as a viable experiment and resume the matched
legacy verification only after storage headroom is restored. Total update burden
remains INCONCLUSIVE; do not adopt/productize on these results.** The decisive
positive evidence is removal of two custom C API adapter definitions and legacy
repair applications from native preparation, with a fresh native build, new exact
binding review and unchanged finite native oracles passing. The strongest
objection is real extra profile/pin/guard bookkeeping for code already absent
from the ordinary native execution path; native already worked on13.0.2 before
this split. This run does not measure net maintenance savings.

The combined run stopped when the matched legacy producer hit the12GiB free
floor during SDK setup. It did not compile. [#138 detailed result](../issue138-paired-capture/RESULT.md)
separates native PASS, legacy missing evidence, branch limits and the aggregate
observation-count correction. Both issues remain Open. A final existing-helper compatibility check also fails
at the first unprofiled generic fixture; see the integration gap below.

## Exact source and implementation

- Start74da0d92c4e165615610c3810bd4415eb3aad140; completed exploration14c3b38a
  and ae1a8465 remains immutable.
- Native producer/host libraries: source_commit
  `4b3954a0faf42986459bc1ee68727be16d67bcbb`.
- Matched legacy-full producer: source_commit
  `32c799031f619164d3730b61a0bc9d7ae48dcd9b` (pushed experiment ref).
- MariaDB13.0.2 source_commit `620a4b5624222048fece7fe1789978ae0675cae2`,
  tag_object_sha `308a50778fb4916ddde0d2923feea3d11dcc92c8`, inspected separately
  with git_identity on the official blob-filtered tag fetch before building.
  [Identity](resume-evidence/target-git-identity.json).
- Native guest `889f21b796c4daaf5244486cce84bfe6a82c758437af400e831d0ed10f0a067e`,
  21237121bytes; linked WASM
  `ba457b19db7d41ea372e72685817bb872dcf7044e1a95512e41bc641dba903e3`.
- Outer runner source is recorded separately from these immutable producer
  sources; actual staged assembler/template/source inventories and new binding
  maps are saved, not old receipts relabelled.

`guest/input.json` explicitly selects native-text or legacy-full, tied to the
route and guest/prepared_source_patch.json. Missing/mismatched selectors reject.
The native overlay is guest/patches/13.0.2-native-prepared.patch; complete legacy
repairs remain byte-identical in13.0.2-prepared.patch. [Both exact descriptors](inputs/)
and [complete inspected pre/postimages](inputs/source-review.json) are retained.
Native also pins the entire deliberately unchanged libmysql.c. Preparation
records the selected profile and observation overlay in provenance.

Native uses the original **before** function proofs for omitted C API repair
families, proving they remain upstream bodies; legacy keeps the original
**after** proofs. Both complete-file profiles pass, and deleting the selector or
editing the complete libmysql.c image is rejected. This is explicit profile
selection, not accepting a failed legacy after-image or broadening a version/body
allowlist. Original component fixtures and guest/source.patch are unchanged.

The ordinary pinned acquisition supplied complete sql_prepare.cc/libmysql.c/
lib_sql.cc. Native SQL PREPARE/EXECUTE's packet==NULL branch uses
set_params_from_actual_params; native binary execution uses setup_conversion/
set_params with the existing conversion snapshot. SQL CALL validation/execution
stays on server SQL paths. emb_stmt_execute assigns MYSQL_BIND/client_params on
the C API path; native initializes client_params=NULL and asserts it remains so.
setup_set_params selects emb_insert_params only for nonnative THDs. The two custom
parameter-metadata adapters have only C API callers. These complete-source paths,
not just patch excerpts, grounded the omission.

| Contact/family | Native trial | Legacy-full / remaining obligation |
| --- | --- | --- |
| mariamem_stmt_parameter_items / metadata | Custom definitions and C API references removed; old metadata-adapter EOF insertion no longer a native patch obligation | Complete implementations and repairs retained |
| MYSQL_BIND unsigned/type/NULL aliases and C API result metadata repairs | Custom repair hunks omitted; upstream embedded functions remain, with exact before-body/full-file proofs | Original repaired after-bodies retained |
| TIME full width | Retained; native packet conversion uses it | Retained identically |
| Embedded Protocol text metadata allocation guard | Retained before strlen, needed by text bootstrap SELECT | Retained identically |
| Native Item conversion snapshot/restore, LONG_DATA, descriptor/reject reuse, charset | Existing native implementation unchanged; original G1/G2 and CALL oracles pass | Legacy original checks still require execution on this new producer |
| THD/NET/Vio/Protocol/auth, atomic SQL/capture, rollback/stop/join | Retained; no queue/credit/deadline/watchdog relocation | Shared/server and route-specific contacts remain |
| WASIX/storage/UCA/auth/routine/toolchain | Same configured shared inputs, plus identical observational hook | Actual complete legacy generation still unverified |

Native SQLprepare/libsql patch sections were rebased to the exact selected full
images, including the decode-counter at actual EOF and TIME context. All other
native patch sections are preserved. [Derivation tool](derive_profile.py) refuses
changed original images. Two investigative failures are retained: the first
identified later initialization-diagnostic insertions; reversing zero-context
legacy insertion hunks failed. The final derivation reads the hash-verified full
archive plus strict portability and requires exact old preimages instead of
guessing offsets. Full native preparation passes with fuzz0; no semantic guard
was bypassed.

## Source, dependency and link evidence limits

The actual native prepared-source manifest, entire prepared-file inventory,
compiler flags/link command, toolchain archives/sysroot inventories, producer
freshness checks and linked-WASM labels are saved under
[138 native evidence](../issue138-paired-capture/evidence/native/).
The full linked-WASM inspection contains32095 defined function labels and neither
custom adapter label. The canonical producer removed its temporary object
archive before collection; the attempted object-archive copy found no file.
We do not claim an object-library symbol inventory or a measured before/after
native link saving. #127 already removed old native exports/reachability, and
linker GC may already have discarded these adapters. Source repair obligations
were removed; a new public API/export reduction is not demonstrated.

The native guest is121bytes larger than the earlier21237000-byte13.0.2 guest,
with the new common observational hook also present. This is neither an isolated
profile size comparison nor a performance result. It is contrary evidence to
using source-line reduction as a runtime benefit.

## Joint #128/#131 cost accounting

| Boundary | Actual evidence | Cost / judgment |
| --- | --- | --- |
| Shared acquisition/setup | Original504 preserved; resumed single original-URL PCRE2 probe verified3088100bytes and original SHA; subsequent pinned dependencies verified | Shared network/setup work, not native benefit; official incident causation unknown |
| Native repair contact | Two C-visible metadata definitions and unused legacy repair applications omitted | One known old metadata EOF repair obligation avoided in native inputs; future elapsed saving unmeasured |
| Profile implementation | Two profiles, full-image pins/proofs, source rebasing, focused negative controls | New real bookkeeping/investigation; not zero maintenance |
| Functional/compiler/link fixes | Native fresh producer passed without a new C++ algorithm repair or compiler/link fix | No evidence native needs an omitted legacy fix in the finite suite |
| Binding work | New bodies/maps/no-op proof/TLS489/ABI16,40,44 reviewed, exact installer body-digest/ABI negatives reject | Still required; old127/128 equality not reused |
| Regression work | Native original79 cases, four original named families and new finite drain scenario passed | Real verification cost; legacy smoke/P1/P2 and paired scenario unrun |
| Storage/lifecycle | Legacy SDK producer stopped at outer free11.98GiB; owned count4.04GiB | Resource failure, not a MariaDB/native semantic failure or speed comparison |
| Total | Partial native success plus new profile cost and missing paired evidence | INCONCLUSIVE; keep experimental, reconsider if continued profile overhead outweighs the removed obligation |

Measured command times and cumulative estimated active/tooling charges are in138.
Acquisition/cache and route programs differ, so none of the command times is a
speed ranking. Future upstream updates must still review remaining native
internal APIs, full images and bindings; unchanged C API before-body guards also
retain a source-review obligation. This split does not make updating free.

No main/release or product-version adoption. Public fd7/12.3.3 preflight remains
separate from this13.0.2 trial; #132/#134 fix the final public tuple. #128's final
candidate-impact check and #129/#130/public bothOS remain pending.

## Existing helper compatibility failure — additional incomplete exit

The post-stop scoped check `pytest tests/test_prepared_source_patch.py -x` fails
at test_exact_apply_and_double_application: the old generic experimental-patch
fixture omits prepared_profile and the new inputs guard rejects it. The focused
new real-target profile tests passed, but they did not cover this existing API
contract. This compatibility check should have preceded the producer; missing
it was a verification-order mistake. It is not a native SQL/runtime failure,
but the source candidate cannot claim passing existing helper tests.

[Failure](../issue138-paired-capture/evidence/helper-compatibility-check.txt).
No original test/expectation was edited and no post-breach source repair was
attempted. Before acceptance, resolve the historical generic experimental mode
versus the new explicit profile contract, preserving the original full-file/
function/preimage and command-failure assertions plus new missing-profile
rejection. Estimate5–15min focused source/helper work; no guest rebuild solely
for a fixture/guard-contract repair if exact engine inputs are unchanged and
that difference is explicitly reviewed. Legacy and branch evidence remain
separately incomplete. This is concrete added integration/maintenance cost.
