# Parameter-order guest binding: runtime comparison next

[Source preflight39607505031](https://github.com/masahitojp/mariamem/actions/runs/39607505031)
passed guest-source and both-OS unit jobs at source_commit
`a342f3065772f21ae4674f4196b8e63c130e0856`. Development-runtime was SKIP by
source-branch design. This does not close the seven unsigned/NULL metadata failures.

The new guest is `4dad84d0b7eba16aa457d23e76fe82d8ae6836dc910545f2203fb5ad8030ba76`,
18,400,809 bytes. [Receipt](receipt.json) binds the linked Wasm, experimental
patch/preparation inventory, toolchain and converter. A clean source worktree's
complete inventory passed dev_guest.verify_guest. Fixed converter730057c,
archive and all13 patches are unchanged, including the actual Go1.26.8
darwin/arm64 converter binary. Canonical guest/source.patch and checked-in
Generated Go remain unchanged.

All three full lifetime functions are byte-identical to the prior41ab4076
fixtures. Full data.bin, all three passive segment ranges, TLS and the complete
Fn67 memory initialization match too. [Binding proof](binding-review.json)
records exact hashes/addresses. The formal source-only adapter and pure owner
transforms PASS. [Raw inventory comparison](raw-inventory-comparison.json)
records all51 raw files:17 changed, including differences outside the binding.
Matching the binding is not evidence that all runtime behavior is unchanged.

The binding accepts only the new guest. The prior41ab4076 joins TIME/P2/P1 and
canonical identities in explicit rejection tests. Local103 checks PASS;
canonical inventory and public-source checks PASS against the unchanged routine
runtime. No installed guest/native runtime result is claimed here.

Reproduction:

1. Use scripts/git_identity.py to inspect a clean checkout of the source_commit.
   Prepare an experiment-workspace (24GiB budget,8GiB floor). Download that run's
   matching guest/source/unit artifacts. Verify the complete source inventory,
   patches, toolchain, optimized Wasm and linked Wasm with dev_guest.verify_guest.
2. Copy [translate.py](translate.py) and [review.py](review.py) into workspace/temp.
   Replace `<repo>` in pinned local Go paths with the local equivalent only where
   applicable; the actual compiler must report go1.26.8. Download the recorded
   converter archive to temp/wasm2go.tar.gz. Run translate.py with Python3.14
   through experiment_workspace.py run --timeout1800, with scoped caches.
3. Run review.py through experiment_disk.py with the same budget/floor.
   verify_translation checks all51 raw files. Review exact functions, full data,
   segment ranges/TLS and Fn67 before changing the binding. setup_candidate.py
   --source-only and atomic/MemFS/lifetime transforms must PASS; do not edit
   generated Go or expand accepted preimages/source-origin exceptions.
4. Update only the single reviewed guest identity and retain older-guest rejection.
   Run the nine focused pytest suites listed in [local-tests.txt](local-tests.txt),
   with pytest8.4.2/PyMySQL1.2.3, plus canonical inventory/public-source checks.
5. Submit prepared-product at its exact new commit. CI builds fresh guest source,
   installs and compiles normally on both OSes, runs SQL/transaction/Snapshot/
   Fork/Close smoke, installed binding/17 mutation checks, P1, original22,
   TIME13, additional20, repair15 and extra2 unsigned controls. All fixed native
   fixtures and failure oracles remain unchanged. Stop after submission.

The first local helper attempt failed on an unused import before translation;
removing that import allowed the same fixed inputs to proceed. No product
source/toolchain correction was needed. Converter source was independently
reconstructed from archive+13 patches before removing its disposable Git metadata;
[cleanup proof](cleanup-source-proof.json) records the complete comparison.
Logs only scrub local paths, with original/stored hashes; SSA/f16 diagnostics
remain visible. Delete owned raw/generated/cache/worktree state after preserving
compact evidence. Independent canonical generation/full J1/P6 acceptance,
main adoption, target version, Qualification and release remain separate.
