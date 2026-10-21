# P2 bounded repairs — source candidate, actual guest verification pending

The Human approved continuing the two-part
[repair proposal](v06x-prepared-p2-blockers.md). This implements a candidate for
the seven raw parameter types and changed-result metadata; it does not declare
those actual guest failures fixed. Local component proofs pass, and the added
native controls establish the expected behavior. The next gate is the new guest
source build, followed by exact identity review and both-OS execution. Main
adoption, version placement, Qualification and release remain separate decisions.

## Changes and semantic boundary

MariaDB source_commit remains83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e;
lite4mariadb24be9371 and converter730057c/13 patches are unchanged. The complete
preimages, postimages, patch and source-function fixture identities are fixed in
guest/prepared_source_patch.json and the
[receipt](v06x-prepared-p2-repair-evidence/receipt.json).

- **Input binding:** extend the seven cases in mysql_stmt_bind_param for WASIX
  embedded builds only. Keep buffer_type unchanged; do not alias BIT/ENUM/SET/
  GEOMETRY/INT24/YEAR/NEWDATE to another SQL type. The numeric cases use the
  established2/4-byte binding sizes and NEWDATE uses the native MYSQL_TIME input.
  Embedded execution still calls the original Item_param conversion by the raw
  type code. Native's unusual NULL behavior for some codes is retained in the
  reference, not replaced with a preferred value. Actual conversion/metadata
  parity still needs the guest gate; accepting a binding alone cannot prove it.
- **Changed result count:** reallocate field metadata and internal result binds
  from the already executed result, clear bind_result_done, and let the bridge
  install current result bindings before fetching. Preserve input binds and the
  original native handle/statement ID. No SQL retry or reprepare is added.
  The previous output buffers remain owned until the new bind is installed.
  Avoid even computing an end pointer using the old count against the new array.
- **Failure handling:** check every metadata-name/default allocation as well as
  the arrays, return on metadata error before preparing a fetch, and close a
  partially rebuilt handle on CR_OUT_OF_MEMORY2008. Other execution errors are
  serialized before result cleanup clears them; cleanup failure or unhandled
  remaining results is terminal, not success. Ordinary duplicate/DATE/etc errors
  must still permit the following SQL, as the unchanged native matrix requires.

New internal behavior is guarded by EMBEDDED_LIBRARY and __wasi__. Ordinary
non-WASIX metadata-count rejection and unsupported binding behavior have negative
component controls. This is not a new general-purpose embedded C API promise:
the resident bridge explicitly rebinds after every execution. The TIME hunk
remains byte-for-byte the previously approved repair and has the same SQL source
postimage. The old prepared_time_patch.json/helper is retained for historical
identity/tests; its repository entry point now rejects use when superseded.
prepare_guest uses the combined exact patch and records experimental_prepared_patch.
Every complete preimage is checked before either file is changed. Failures,
changed inputs, changed proof functions and repeat application are rejected.
Canonical guest/source.patch and release's experimental-patch rejection are intact.

## Evidence and limits

| Check | Result | What it establishes |
| --- | --- | --- |
| Complete original source → combined patch → complete postimages, checked proof extracts, repeat rejection | PASS | Fixed source application; no fuzzy/source drift acceptance |
| Focused89 checks on macOS arm64 | PASS | Patch guards, real extracted source functions with mock dependencies, owner cleanup, existing binding/tooling guards and new oracle negative controls |
| Source-function before/after controls, normal and address/undefined sanitizers | PASS | Before: all7 rejected, changed count2057. After:7 accepted with type codes intact, counts grow/shrink without a second execution, input binding retained |
| Metadata allocation failure injection | PASS, component scope | Each of16 allocations for two columns fails separately, including name/default copies; error2008, no fetch, one execution. This is not full engine/allocator fault coverage |
| Fixed native12.3.3:15 added controls and replay | PASS | Both unsigned flags, NULL/non-NULL/reused descriptors, integer→raw-type transitions; grow/shrink with a counter advancing exactly once per execution and healthy following SQL |
| Unchanged native20/22/TIME13 references replay | PASS | Prior expectations are not edited to accommodate this candidate |
| Canonical generated inventory/public-source checks | PASS | Existing canonical runtime intact; not a new guest PASS |
| New guest Wasm/source build | PENDING | Source/unit preflight CI on experiment/prepared-p2-repair |
| New allocation/lifetime functions, data/TLS binding and installed runtime | PENDING | Review actual new output before using its identity; no allowlist/guard bypass |
| Both-OS actual guest: previous gates plus20 and15 repair cases | PENDING | Needed before judging the eight failures repaired |

The component source fixture retains upstream copyright/license notices. Its
before/after functions are compared verbatim with the complete source during
preparation, so a hand-written imitation cannot stand in for the source being
built. Dependencies in the component proof are mocks: these results cannot prove
MariaDB engine semantics or complete ABI/lifetime behavior. Native is the pinned
Linux arm64 container on macOS, not macOS-native MariaDB or Ubuntu x86_64 guest.
No new performance measurements or broad compatibility claims are made.

[Local tests](v06x-prepared-p2-repair-evidence/tests.txt),
[complete source application](v06x-prepared-p2-repair-evidence/patch-application.json),
[native repair replay](v06x-prepared-p2-repair-evidence/native-repair-replay.json)
and the receipt preserve exact evidence/hashes. P2 as a whole and P3–P6 remain
unfinished, including canonical independent regeneration. This source preflight
cannot satisfy those gates.

## Reproduce and continue

Use Python3.14 with pytest8.4.2 and PyMySQL1.2.3, and inspect source identity with
scripts/git_identity.py before builds. Run the focused owners:

```sh
python -m pytest -q -rA tests/test_prepared_source_patch.py \
  tests/test_prepared_api.py tests/test_prepared_time_patch.py \
  tests/test_prepared_p2_repair_probe.py tests/test_prepared_p2_matrix.py \
  tests/test_routine_schema.py tests/test_thread_lifetime_binding.py \
  tests/test_dev_guest_tools.py
python scripts/verify_generated_runtime.py
python scripts/check_public.py
```

For native replay, use the receipt's exact image digest, empty root password,
database test and a loopback-only published port; stop the disposable container
afterward. Run the new probe with --native-port PORT --reference
tests/fixtures/prepared-p2-repair-native.json --output native-repair.json. Original
probes/references remain unchanged. New guest runs use --host instead, with a
fresh root DB/host per case and retained failure/log/teardown evidence.

Source preflight deliberately skips the development runtime on this branch:
the new Wasm is not yet the single reviewed identity. After that build, inspect
the actual guest and raw converter output through the existing formal route,
review all allocation/lifetime bodies and data/TLS, update the exact binding only
when justified, then submit the full prepared-product gate. CI still contains
all prior runtime checks plus the15 added controls. Do not retry the SQL, change
expected bytes, relax identity checks, or silently declare a failure out of scope.
