# P3 CALL guest binding: actual execution next

[Source preflight39624071363](https://github.com/masahitojp/mariamem/actions/runs/39624071363)
finished guest-source and both supported-OS unit jobs successfully at
source_commit `46f5c2c079b350ef279f0d997075f8be84d3ca16`. Development-runtime is
SKIP by source-branch design. The first API read still reported an in-progress
aggregate; only the final job conclusions are used here. This is not a CALL
runtime PASS.

The [receipt](receipt.json) binds the clean source inventory, complete preparation
inputs, guest and linked Wasm, toolchain, converter binary/archive and all13
unchanged patches. Guest SHA256:
`e6d6021a5753492169aeacbbc787e693e1730026b6da9960ef8c6ace296ac37a`,
18,402,732 bytes. The actual darwin/arm64 converter binary matches the previously
reviewed430bf085 identity. This is one UNQUALIFIED source build, not independent
canonical generation or Qualification.

## Exact binding review

[Observed differences](layout-review.json), full function diffs and the complete
memory-initialization diff establish this limited relation to prior P2 guest4dad84d0:

- Fn131 is byte-identical. Fn153 has48 changed literal occurrences and Fn214
  has62; all are BSS addresses shifted by64. Every other numeric literal and
  all nonnumeric source structure match. The address pairs are enumerated, not
  inferred from one sample. The functions' paths/names/calls/offsets are unchanged.
- Data segment0 grows64 bytes (6,212,966→6,213,030). Segment1 keeps642,620 bytes
  at its new address14,601,664. TLS moves15,244,224→15,244,288, with exactly the
  same505-byte content and SHA25611982067. Full data.bin and segment1 hashes
  change and are recorded; full-data identity is **not** claimed.
- The complete Fn67 initialization changes only the enumerated length/address
  constants. The first segment destination stays8,388,608. BSS moves
  15,244,736→15,244,800, retaining8,982,576 zero-filled bytes; its end/initialization
  guard moves24,227,312→24,227,376. Inter-segment/TLS/BSS padding stays26/4/7 bytes.
  Every changed Fn153/Fn214 reference remains at the same relative position in
  that zero-initialized BSS region. Argument/object-relative offsets used by the
  handwritten lifetime owner are unchanged. Full initialization is pinned too.
- This is an **offline comparison of one observed layout**, not an installer
  normalization rule. The owner still requires the exact complete function
  hashes, literal addresses and one exact guest identity. The previous P2 guest
  joins all five earlier rejected identities. Mutation checks use the current
  literals and continue rejecting nearby or unrelated relocations.

The formal source-only adapter and pure atomic/MemFS/lifetime transforms PASS
with the newly pinned preimages. [Raw inventory comparison](raw-inventory-comparison.json)
records every raw output file; neither layout analysis nor the three function
pins establishes unchanged whole-runtime behavior. Actual installed guest tests
must follow. No generated Go is hand-edited; canonical checked-in Generated Go
and canonical source.patch/converter patches remain unchanged. The historical
prepared-p2-binding fixture directory now contains the current staged P3 preimages.

Local107 focused pytest checks PASS, including C/sanitizers, old-guest rejection
and complete-initialization mutation checks. Canonical inventory/public-source
checks concern the unchanged routine runtime/current source respectively. No
new guest installation/compilation/runtime PASS is claimed locally. Previous
source-preflight Go race tests ran on both OSes at46f5c2c; only Python ownership/
fixture/comment changes follow here, so those unchanged Go packages are not
rebuilt locally again.

## Reproduce and continue

1. Inspect scripts/git_identity.py on a clean source_commit46f5c2c worktree.
   Download matching guest/source/unit artifacts. dev_guest.verify_guest must
   verify its complete source, overlays/patch pin, toolchain and both Wasm hashes.
   Do not widen origin exceptions because the binding script changes later.
2. Follow the [prior formal translation recipe](../v06x-prepared-param-order-binding/reproduce.md)
   with the new artifacts, actual Go1.26.8 on PATH, Python3.14 and fixed converter
   archive. Use a24GiB budget/8GiB floor and scoped disposable caches. Verify all
   raw output files/converter patches with dev_guest.verify_translation.
3. Copy [inspect_fast.py](inspect_fast.py) and [check_owner.py](check_owner.py) to
   workspace/temp. The former compares old fixtures in the clean origin worktree
   with raw output and records full diffs/init/segment declarations. Review all
   layout differences above before updating root's fixture/owner hashes. The
   latter applies the formal source-only adapter and current root owner pins,
   checking complete bodies/data/TLS/init. It never edits generated output.
4. Run the ten scoped pytest suites from prepared-product.yml (pytest8.4.2,
   PyMySQL1.2.3), canonical inventory and final public-source/diff checks. Verify
   saved evidence checksums after all helper files have been written.
5. Push the exact new prepared-product candidate. CI rebuilds fresh guest source,
   installs/compiles the new runtime on both OSes, then runs SQL/transaction/
   Snapshot/Fork/Close smoke, installed binding/18 mutations, P1 and all72 P2
   scenarios, followed by the P3 minimal OUT+two-results native comparison.
   Preserve failing raw packets/stage/errno/SQLSTATE rather than dropping results.

An initial inspection helper scanned each function repeatedly and was interrupted
after the efficient single-pass inspection had saved the same necessary evidence.
No build/test failure or correctness workaround resulted. Converter source was
independently reconstructed and compared before deleting its temporary Git
metadata; compact proof is retained. Synthetic test Git histories are bundled
before scratch deletion. Remove generated/adapter trees, downloads, venv/caches
and the completed clean worktree after preserving evidence.

Actual minimal CALL PASS is still required before the full P3 matrix. Full P3
(capability truthfulness included), P4–P6, final canonical/J1 acceptance, main
adoption, target version, Qualification and release remain unfinished.
