# Minimum routine bootstrap — implementation results and Human Review

2026-10-20. **macOS arm64 implementation checks PASS; native Ubuntu confirmation
is pending candidate CI. Recommend reviewing this bounded candidate after that
CI, without advancing version placement or main adoption now.** Ordinary Start
makes the minimum procedure/function cases usable immediately; Snapshot/Fork
preserves routine rows and child independence. Incompatible restored definitions
fail before ready and release their resources rather than being repaired.

The strongest objection is that this installs **only mysql.proc**, not a complete
MariaDB system schema. It does not establish account/DEFINER/privilege or general
dump compatibility. Public multi-result CALL also depends on accepting the
separate experimental text-result bridge. The opposite-platform/default Connector gates are not yet
satisfied. Those are explicit conditions for the next Human Review, not inferred
release approval or reasons to expand this implementation into install-db.

## Approved scope and source identity

The Human approved the [design](v06x-routine-bootstrap-design.md), including the
product-managed proc-structure boundary and rejection of incompatible restored
baselines. This is not Fresh-only. Routine rows remain normal mutable child
state. Version placement, prepared/multi-statement adoption, main integration,
Qualification and release remain separate decisions.

Branch: `experiment/routine-bootstrap`, based on design
`1f4599f28fe480d88e3c0b8cd18e7d7aa49992c0`, which follows feasibility
`46ff987f85b576d6664f3cafcc89e481326de51f`. Main at start remains
`de0e08a9c4248969a7522abebfdee8aea6ef9657`. Do not merge this experiment's
prepared/feasibility history wholesale.

| Input / artifact | Exact identity |
| --- | --- |
| Fixed guest build source | `dd6438a6da76ef9ed85ceb47d861d24112330b84` |
| Tested ordinary host/generation source | `1e2834c20baa0c3596d6cb32e61f137b11d52dc5` |
| MariaDB / lite4 | `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e` / `24be9371a2f6c71250a2356631ad6feab2280b02` |
| MariaDB archive SHA256 | `36319b89c4373cf35e5c5c08686625eccae2816257b6982a4815ff552b945845` |
| Converter | `730057c146463f663e8774587bc96fb2bea91af8` + unchanged existing 13 patches |
| Guest Wasm | `118ef83ee066d57f946603f7e2a2b2c60d9b5f1cd4d627c3d18a73cbd963350c`, 18,442,821 bytes |
| Ordinary macOS host | `1eb79b527c16ade9001f60b9a451021c703214d745357c4366e0bad6e4c95b2b`, 100,188,354 bytes |
| Installed 99-file inventory SHA256 | `0d61b8ed497057b3cb54337402e0be00f0d402f222315512d9acae2a173d4bb3` |

Commit objects were checked with `scripts/git_identity.py`; upstream identities
and native image/source revision reuse the [feasibility evidence](v06x-guest-system-schema-spike.md#basis-and-exact-inputs).
See the [new evidence index](v06x-routine-bootstrap-implementation-evidence/files.json):
`fixed-guest-record.json`, `fixed-patch-identities.json`, `fixed-development.json`,
`fixed-provenance.json`, `fixed-independent-raw.json` and
`fixed-independent-install.json`. The last inventory hashes sorted compact JSON
of relative filenames and SHA256 values, **including provenance**.

Both independent development routes use the same fixed guest. All 52 raw-module
files match. Re-running the official installer with one identical bound input
record matches all 99 files, including provenance, without exclusions or byte
normalization. Independently acquired installation records have different real
output paths; they are not relabelled identical inputs. This is not independent
Wasm Qualification: there is one successful fixed-source local guest build.
CI will build it again from source and check the explicit byte binding.

## Implementation and ownership

- `scripts/routine_schema.py` verifies the adopted source version/commit, whole
  SQL-file hash and unique proc-DDL hash, then derives the signature and generates
  a GPL-attributed include. `guest/routine_schema.json` contains the independently
  reviewed native 22-column signature. Source/DDL drift fails closed.
- `guest/routine_bootstrap.inc` is an authored overlay. Fresh creates mysql and
  the exact official Aria proc table on the private connection, restores database
  selection/session sql_mode, and validates before ready/workers. Charset/global
  defaults are unchanged. Full base/fix scripts and mysql_version are not used.
- Restore performs read-only validation: column order/name/type/collation/NULL,
  primary-key order and Aria engine. Missing/incompatible **checked signature**
  fails; no CREATE/ALTER/repair or routine-body scan occurs. Additional compatible
  metadata is not claimed to be exhaustively audited.
- Fresh/restore comes from the same internal `restore != nil` decision as mapped
  entries, transported by an explicitly constructed environment. Ambient mode
  values are ignored. Missing/invalid/contradictory mode fails. The generated
  diagnostic driver receives the same rule through its deterministic adapter;
  existing explicit auth diagnostics retain their bypass.
- `runtime_instance.go` and its test are explicitly `HANDWRITTEN_FILES` owners.
  Transpiled Go was not edited. Canonical `guest/source.patch`, the existing
  experimental patch and all 13 converter patches are unchanged; preparation
  records the additional authored overlay/header separately.
- New exact lifetime binding reviews Fn216→214, Fn217→215 and Fn221→219 plus
  fixed data relocations. Body hashes and mutation rejection remain strict;
  canonical bindings are intact. The unchanged J1 assertions run against the
  actual new functions/data on heap/mmap, with and without race instrumentation.

The checked-in canonical transpiled guest/release inventories remain the prior
product baseline. Successful runtime checks use the normally regenerated
**isolated development product**, not a claim that `go get` of this branch already
selects the new guest. Only authored owners/adapters are changed in place.
Canonical promotion is an unfulfilled adoption step, coupled to the separate
text-result decision; this experiment is not merge-ready as a whole. Later
candidate commits add docs/tests/CI requirements, not ordinary runtime changes;
CI performs a fresh guest build for that exact final SHA. No source-origin
allowlist was expanded to reuse the earlier local record across workflow changes.

Every MariaDB update requires review of the pinned DDL/native signature, source
hashes and generated output, plus the existing positive/negative fixtures. This
adds no generic schema upgrader. Promotion still needs minimal canonical source,
license/provenance/release-inventory bookkeeping and the separately approved
text multi-result path; current canonical release pins are intentionally not
changed by this UNQUALIFIED experiment. Release guards were not weakened.

## Results and failure oracles

| Gate | Result | Evidence / exact limit |
| --- | --- | --- |
| Source, schema/C-helper, origin and exact binding tests | PASS, 55 | `fixed-input-tests.log`; helper SQL/metadata failure injection is an isolated native C API shim, not an injected real-guest DDL error |
| Formal guest build, translation and compilation | PASS | `guest-build-c.log`, `dev-fixed-native.log`; Linux arm64 source builder, native macOS Go 1.26.8 |
| Independent regeneration | PASS, 52 / 99 | Fixed guest; raw modules and identical-input official installation as above |
| Existing development SQL/transaction/Snapshot/3-child/cleanup smoke | PASS, twice | Both fixed development-route logs |
| Immediate routine/native-control parity | PASS, 6/6 | First test in `routine-runtime.log`; unchanged six-case oracle from `benchmarks/spikes/guest-system-schema/probe.py`, native results in `native-routine-cases.json` |
| Routine state through Fork/recapture/Close | PASS | Concurrent child row changes70/700, original baseline7, recaptured child70; live children survive baseline Close |
| Invalid restored structure | PASS rejection | Missing table, NULL mismatch and reordered primary key; two failed Fork attempts each, same-host healthy sibling remains usable, owner references unchanged |
| SQL-only1728 oracle | PASS | Separate running-DB fixture; not replaced by pre-ready validation |
| Failed-start lifetime/resources | PASS | `go-routines.json`: nil server, per-failure creates/releases+1, unchanged active/reserved/RW mapping counters, no transfer-directory residue, bounded Owned.Close proves read-lease release; unrelated DB still queries |
| Full ordinary Go probe lifecycle | PASS | Total 9 mapping creates/releases; final active/reserved/RW counters0 and release failures0. These are allocator counters, **not RSS** |
| Existing prepared bridge / wire / auth diagnostics | PASS | `prepared-regression.json`, `wire-unit.log`, `auth-diagnostic.log`; prepared CALL is not claimed |
| Boot-mode ownership | PASS | `mode-unit.log` + C shim; per-instance slices and ambient values, invalid/missing/contradictory modes |
| J1 logical failure/protection | PASS oracle | Six heap/mmap runs: unprotected early-free exits1/canary165→1 with controls passing; protected runs exit0, including -race. Zero race reports are not a general shared-memory proof |
| CREATE EVENT | PASS unsupported1235 | Asserted in the immediate guest test; still outside routine support |
| Native Ubuntu x86_64 acceptance | SKIP locally / pending CI | Workflow `routine-bootstrap.yml` builds the guest then runs both native platforms. No Ubuntu PASS is claimed here |
| Connector/Python in this local environment | SKIP | PyMySQL 1.2.3/Python 3.14.8/OpenSSL 4.0.3 used. Connector 26.7.0 import limitation here was already recorded in feasibility; CI explicitly installs 26.7.0 and requires its default connection/text CALL/prepared expression test. Do not relabel PyMySQL as Connector evidence |
| Qualification / release / main integration | SKIP by boundary | Not authorized by the implementation decision |

Normal diagnostic failures retain the existing guest_ready wrapper (including
existing Proc_exit2 text); the actionable `routine_bootstrap` stage, MySQL
errno/SQLSTATE, reason and re-preparation/bug-report guidance remain visible.
No new public error family or quiet retry-as-Fresh was added.

The first implementation had an actual bug: `SET SESSION.sql_mode` returned4081.
The official smoke rejected it before ready. It was corrected to `SET SESSION
sql_mode`, checked on native with unchanged sql_mode/database/charset, and rebuilt
from fresh source. Old/new Wasm code and all other core sections are byte-equal;
data changes are exactly two 46→32 substitutions. See `corrected-sql-native.json`
and `corrected-wasm-sections.json`. The original failed smoke remains FAIL in its
raw log; its real Fresh failure separately demonstrated mapping/temporary cleanup
(`fresh-failure-cleanup.json`). The Python 3.9 disk-monitor failure stopped another
attempt; that container was explicitly stopped and the clean build used 3.14.
Neither interrupted/failed attempt is counted as the fixed-source build.

## Diagnostic cost, not a performance target

Wasm grows 6,003 bytes relative to the prior prepared guest 18,436,818 bytes.
The ordinary candidate, six small-fixture Python Fresh→Snapshot→Fork pairs,
has median API times: **Fresh 59.95 ms, Snapshot 3.06 ms, Fork 42.42 ms,
Close 2.42 ms**. Fresh spans 52.87–250.62 ms; the first 250.62 ms sample is retained.
This has no old-guest control and does not establish a regression or its cause.

The library does not export its in-memory startup timing file through normal
DB-data export. The initial direct collector correctly failed to find it; that
failed diagnostic is retained. For decomposition only,
`tests/v06_routine_timing/prepare_overlay.py` creates a checksum-bound compiler
overlay of the **handwritten** adapter. It copies the existing timing file only
**after guest execution has ended**, without touching candidate/generated files.
The separate diagnostic binary and overlay hashes are in
`timing-overlay-identity.json`; its guest is the identical 118ef83e Wasm. The
candidate 99-file inventory remained unchanged. This overlay is not a product
runtime change or Qualification evidence.

Six paired modes in one warm Go host, each engine newly started, yield:

| Existing guest-clock interval | Median | Range |
| --- | ---: | ---: |
| Fresh routine creation + metadata validation | **1.78 ms** | 1.53–2.41 ms |
| Restore metadata validation | **0.91 ms** | 0.886–0.979 ms |

See `guest-timing.json`, `cost-summary.json`, `cost.json` and `cost-traces/`.
These direct intervals exclude effects of having system-table files during the
preceding engine initialization. They are not an old/new total-startup delta,
an Ubuntu result, or a guarantee. General initialization tuning remains separate.

## Next Human Review

First obtain native CI receipts for the exact submitted candidate. Then decide
routine version placement and the canonical adoption scope with the text-result
prerequisite; do not infer either from implementation approval. Full install-db,
accounts/privilege coverage, prepared CALL, events, broad compatibility discovery
and final Qualification/release remain outside this report. There is no observed
functional blocker in the bounded macOS cases; opposite-platform acceptance and
promotion bookkeeping remain unfulfilled adoption conditions.

No runtime rework is recommended from the current minimum-case evidence. The
case for proceeding is immediate usable routines with finite failure/isolation
proofs and a small measured gate. The strongest counter remains that these
minimum cases do not qualify every routine-containing migration/dump or replace
the outstanding adoption decisions.
