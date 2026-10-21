# P2 repair guest binding — actual runtime comparison next

[Source preflight39596726209](https://github.com/masahitojp/mariamem/actions/runs/39596726209)
passed guest-source and both-OS units at source_commit
68fb5c247e273192565789246abcb34733a20bc1. Each unit job passed91 checks and the
three Go package race suites. Development runtime was SKIP by branch design.
This closes source compilation, not the eight actual guest failures.

[Receipt](receipt.json) records the exact source, guest, converter and evidence
identities. New guest SHA256:
41ab407681f537daed9b8f2d9c0ef5edc584f7d598399dd8d42ed8e1b13a0be0,
18,400,783 bytes. It is a single UNQUALIFIED source build. The converter archive,
commit730057c and all13 patches are unchanged; the actual Go1.26.8 darwin/arm64
converter binary matches the previously reviewed430bf08585f68513 identity.

## Binding review

- Full Fn153/Fn131/Fn214 bodies are byte-identical to the prior P2 fixtures,
  including every address/constant. Their existing exact hashes stay unchanged.
- Full data.bin, all three segment ranges and505-byte TLS match the prior guest.
  Additionally inspect Fn67's initialization: segment0 at8388608, segment1 at
  14601600, TLS at15244224 and BSS fill starting15244736. Data-byte identity alone
  would not establish those placements. Pin the complete initialization body in
  memory-init.txt and reject its offset mutation in the installed-output checker.
- The formal source-only adapter and pure atomic/MemFS/lifetime transforms pass.
  This is not full installation, compilation or guest execution. No generated Go
  is hand-edited. The canonical checked-in runtime remains the old routine guest.
- Raw inventory has30 changed files of51, including aliases, generated.go, base
  and part files. Matching the three allocation functions/data does not establish
  unchanged whole-runtime behavior. Preserve the complete comparison, then test
  actual guest behavior through the existing native oracles.

The lifetime owner now accepts only the new guest hash. Rejection includes the
immediately previous TIME guest3bfb1030, initial P2 guesta52dd707, P1 guestc42f1c64
and canonical baseline976bbc58; no alternate identity or permissive source-origin
path is added. Local94 checks PASS, including those rejection cases, the new
memory-initialization mutation, all existing patch/API/tooling controls and
unchanged canonical inventory/public-source checks. Saved source/translation/
binding/data/owner reports and raw inventory give the precise boundaries.

## Reproduce and continue

1. Inspect source identity with scripts/git_identity.py. Use a clean checkout
   of the source_commit above. Download that run's matching unqualified guest
   and verify the complete source inventory, preparation/experimental patch,
   toolchain, guest Wasm and linked-Wasm hashes. dev_guest.verify_guest must pass;
   the changed binding script is not justification for broadening origin reuse.
2. With actual Go1.26.8 and Python3.14, run the existing translate_guest.py with
   explicit --guest, --guest-sha256, --converter-archive and fresh --output.
   Verify the complete translation with dev_guest.verify_translation. Use the
   recorded converter archive/13 patch hashes, not another installed converter.
3. Run setup_candidate.py --source-only with that module, guest and explicit raw
   input-manifest. Apply the owner transforms to formal adapter output for the
   pure checks; raw base is not the MemFS adapter preimage. Compare complete
   lifetime bodies, full data, TLS, segment declarations and initialization body.
4. Run the eight focused suites listed in local-tests.txt with pytest8.4.2 and
   PyMySQL1.2.3. The source-build units have91 tests; the post-binding set has94.
   The installed lifetime/checker suite now has16 tests. None of these local
   results substitutes for actual guest/native comparison.
5. Submit prepared-product with the reviewed binding. Its CI builds fresh guest
   source at that exact candidate, installs normally, compiles, runs SQL/
   transaction/Snapshot/Fork/Close smoke, then exact installed binding/mutations,
   P1, original22, TIME13, additional20 and repair15 native comparisons on both
   OSes. Preserve failure artifacts; expected fixtures remain unchanged.

Independent canonical generation and full J1/P6 acceptance remain unfinished.
Do not mark the eight failures repaired, or P2–P6 complete, until their actual
gates pass. Main adoption, version placement, Qualification and release remain
separate. Logs scrub only local absolute paths; original/stored hashes are in
the receipt. Existing SSA/f16 diagnostics are retained without converter changes.

Workspace used a24GiB budget and8GiB free floor, with scoped Go caches. Converter
source was independently reconstructed from its archive plus13 patches and
compared before deleting disposable Git metadata. Preserve compact evidence and
committed inputs; remove downloads, raw/adapted modules, venv and caches afterward.
