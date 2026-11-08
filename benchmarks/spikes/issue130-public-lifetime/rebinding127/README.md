# Source-only #127 rebinding preflight

Question: can the exact #127 guest be authenticated and rebound to the integrated
settings/lifetime candidate without pretending that an old C2 receipt produced it?
Parents:46915e50c12795da4787c9d1ee0b73e6c6a829dc and
2fc03f5058e94aa17fef9d72473ccb4e8401a80d, merged as exact ancestors.
Exit: source/provenance tests and an explicit bounded producer/staging proposal;
if the complete producer bundle or proper origin is missing, report that gap.
No builds, staging, runtime, CI or benchmarks. Remaining original 2h active /
30min tooling ceilings apply; this final source-only slice targets <=5min tooling
and does not create a new harness. No additional build budget is authorized.

## Conclusion and exact boundaries

Source slices merge without conflict; three focused provenance/preflight tests
and the existing13 settings/lifetime source tests pass. No current executable
C2/new-guest staging mode is claimed. Keep both old C2 scripts/receipts and
#130's strict overlay unchanged until a separately approved rebinding patch.

The old tuple remains be244a0b + d4f30818 + P1-b binding; the new tuple is:

- Guest producer and runtime installer source_commit:
  `8c8b5f1c09765c9fb51c2b640ed2fc32d759fbe3`.
- Guest SHA256:
  `873c9daf38f6e7f5005dbdbdf8e920b396fe5591ab74bfedcad37b436c50d3dc`.
- Binding: `benchmarks/spikes/issue127-bootstrap/binding/identity.json`, SHA256
  `35fb98fda9d89c0a6010b32f6be63446d2684b73d69837322fd905e3aeb478f0`;
  entryFn520, TLS489, ABI16/40/44, with explicit recorded relocation review.

The existing `verify_guest` authenticates the complete source identity,
tool/overlay hashes, guest/linked bytes and build repetition. `install_inputs`
reopens that guest and translation bundle; `generate_runtime` verifies the exact
experimental guest/worker/ABI/body binding. None of these controls is changed.
`verify_source_origin` allows only its narrow docs/tests/three-script drift:
this integrated checkout differs from8c8b5f1c in disallowed benchmark paths, so it
cannot silently replace the guest-origin checkout. The three scripts remain
byte-identical to8c8b5f1c. Run the verifier and installer **from the exact clean
8c8b5f1c producer/installer checkout**, separately from integrated host/observer.

The retained `guest.json` honestly says incremental continuation and
`fresh_canonical_builder_success=false`. The unchanged verifier does not itself
require that flag to become true, so a fresh corrected build is an explicit
next-wave acceptance condition, not a PASS inferred from verifier source.
No complete guest/linked/translation/install bundle or C2 public source/binary
receipt is retained. Saved JSON and normalized phase records cannot be supplied
as if their missing byte bundles existed. This is the concrete blocking input
for actual staging, not grounds to bypass origin checks.

## Bounded next-wave proposal (not executed or budget-authorized)

1. Assign a heavy-build owner and agree the budget before work. Prepare an exact
   clean8c8b5f1c source checkout in a fresh Linux arm64 root builder with the locked
   LLVM23/WASIX/Binaryen tools, empty `/work`, absent SDK and external `/output`.
   Preserve12GiB free floor /12GiB owned ceiling and60min timeout from #127.
   Inside that checkout the existing commands are:

   ```sh
   python3 scripts/git_identity.py inspect HEAD
   python3 benchmarks/spikes/issue127-bootstrap/build_checked_guest.py
   PYTHONPATH=scripts python3 -c 'from pathlib import Path; from dev_guest import verify_guest; r=verify_guest(Path.cwd(), Path("/output/artifact")); assert r["source_commit"]=="8c8b5f1c09765c9fb51c2b640ed2fc32d759fbe3"; print(r["guest_sha256"])'
   ```

   The second command owns the fresh canonical builder invocation and prepared
   source check; do not call the historical resume script to claim fresh PASS.
   Save complete `guest.json`, `mariamem.wasm`, `linked.wasm`, logs/tool/prepared
   identity. Compare fresh guest to873c9daf. If different, stop for a new exact
   binding/relocation review rather than replace the expected hash. Verify all
   producer fields against actual source/bytes, never a copied old C2 receipt.
2. Before staging, implement a small explicit **two-tuple** selector in the C2
   adapter (or a candidate-specific wrapper): old be244/d4/P1-b and exact
   8c8b/873c/Issue127 binding. It must invoke the unchanged `verify_guest`,
   `verify_translation`, `install_inputs` and installer from the selected exact
   origin, with the new binding file supplied by its reviewed observer commit.
   No generic arbitrary-origin mode or broad verifier allowlist is proposed.
   Retain source-only negative tests for old/new tuple mixing and wrong binding.
3. Use the existing origin checkout's `translate_guest.py` with explicit
   `--guest`, new exact `--guest-sha256`, locked `--converter-archive`, and fresh
   `--output`; use `setup_candidate.py --source-only --source-module ...
   --guest ... --input-manifest ... --output ...`. Generate new live-directory
   UNQUALIFIED installation inputs as C2 currently does; call the origin's
   `scripts/generate_runtime.py --source-module ... --development-input ...
   --development-thread-binding REVIEWED_127_BINDING --output NEW_RUNTIME`.
   Recheck the completion/lifetime overlay's exact preimage and preserve native
   factory/legacy tripwire; record all inventories and distinct installer/host/
   observer origins. These are real scripts/arguments, but artifact paths and
   install receipts cannot be populated until step1 succeeds.
4. Emit a **new** public source receipt for the new tuple; do not edit the old
   be244/d4 receipt. Explicitly adapt #130's guest gate to a reviewed exact127
   mode only after producer authentication. Its pinned backend/relay/capture
   bytes still match a5ee1ed9, so no weakening of those preimages is needed.
   A different frame/profile/INSPECT/runtime completion contract would require
   separate adaptation even though this source spike declares them unchanged.
5. The new public receipt → new lifetime derived receipt → settings observer
   chain must retain the new producer8c8b and guest873c unchanged. The existing
   settings receipt selector can then use a separate base/derived pair; fresh
   root/control/host binaries and wheel need their own hashes. Old C2 binary
   hashes and #127's isolated native PASS are not public settings/fault evidence.

Planning evidence from #127: full compilation/tool acquisition about20min,
continuation about5min, native host compilation about5min; translation/setup and
public fault/consumer acceptance cost remains unmeasured. Recommend first
reserving one60min producer window plus15min setup/preflight and a separately
agreed translation/host window, with no automatic retry/CI or full acceptance
campaign. Rebinding implementation/source tests are a separate bounded small
patch; the present worker's remaining tooling allowance is insufficient to
implement and validate that executable two-mode staging path. #128's update
trial remains another worker; #129/#130/#132 acceptance, #134, main adoption and
release remain unapproved/unexecuted here.

Full public-source guard:PASS (7701 files); touched Python compile and diff checks
PASS. Owned test bytecode/guard output are removed; old build files and other
worker state are preserved. Remaining tooling is estimated below5min, not enough
for executable rebinding implementation/validation; no budget expansion used.
