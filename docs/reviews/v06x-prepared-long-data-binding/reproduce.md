# P4 LONG_DATA exact guest binding — runtime acceptance pending

[Source CI39714836816](https://github.com/masahitojp/mariamem/actions/runs/39714836816)
completed successfully at source_commit425c821ac1c06fa0cca2f9a6c14109c066c08501:
guest-source and both supported-OS unit jobs PASS. Development-runtime was
SKIP by source-branch policy, not a runtime PASS.

The complete [verified guest receipt](guest.json) binds the clean source inventory,
MariaDB/lite4mariadb inputs, toolchain, overlays and linked/optimized Wasm.
New development guest SHA256 is
`f5ce001d5bad34e766c3f92b6d83f429ad6767153971fc219b52d37563fb496a`
(18,404,230 bytes). This is an UNQUALIFIED source build, not canonical adoption
or independent release regeneration.

## Binding review

The formal fixed-converter translation succeeds. [Translation inputs](translation-inputs.json)
retain the same converter commit730057c, archive1adc74bb, darwin/arm64 binary
430bf085 and all13 canonical patches. Their identities are checked against the
prior P3 translation, not reconstructed from alphabetical receipt order.

[Complete function inspection](binding-inspection.json) and
[layout review](layout-review.json) establish:

- Fn153/Fn131/Fn214 are byte-identical to the accepted P3 preimages. Their complete
  hashes and exact handoff remain unchanged. The complete Fn67 initialization
  and segment declarations are also byte-identical. Empty full-body diffs are
  saved; no numeric normalization is used for installer acceptance.
- All three segment ranges and memory destinations remain fixed. TLS retains
  exactly505 bytes and SHA25611982067. BSS start15,244,800, length8,982,576 and
  initialization guard24,227,376 are unchanged because the complete initializer
  is identical. This does not establish equivalence of other generated functions.
- Full data.bin and the first two segment hashes change. New identities are pinned
  explicitly; bytewise equality of those contents to P3 is not claimed. Every raw
  output file is recorded in [inventory comparison](raw-inventory-comparison.json).
- The owner accepts only the new exact guest. Prior P3 joins the earlier explicitly
  rejected identities. Existing complete-function, relocation and initializer
  mutation oracles stay in place. Canonical checked-in Generated Go is unchanged.

[Formal source-only adapter and pure owner transforms](owner-checks.json) PASS.
These checks do not compile or execute the new guest. Focused local Python/C
checks, including sanitizers and old-P3 rejection, PASS; the unchanged canonical
inventory check concerns only the old routine runtime. Actual LONG_DATA25 and
previous P1/P2/P3/lifetime/smoke regressions must run on both supported OSes next.
No feature/P4 completion, main adoption, Qualification or release is asserted.

## Reproduce

1. Use scripts/git_identity.py on a clean425c821 worktree. Download matching
   guest/source/unit artifacts from39714836816 into workspace/temp/ci. Keep the
   origin worktree clean: verify_guest checks its complete tracked inventory.
2. Prepare a disposable workspace with24GiB budget and8GiB minimum free space.
   Copy translate.py, inspect_fast.py, layout_review.py and check_owner.py here
   into its temp directory. Download the fixed730057c converter archive to
   temp/wasm2go.tar.gz. Use Python3.14 and actual Go1.26.8 on PATH.
3. Run translate.py through experiment_workspace.py run using its **absolute**
   path (the runner changes cwd to worktree). An initial relative-path invocation
   failed before translation; no runtime/build evidence resulted from that attempt.
   Then run inspect_fast.py and layout_review.py. They compare against clean-origin
   P3 fixtures and complete prior translation inventory; inspect differences before
   changing root's owner pin/fixture identity.
4. Run check_owner.py after applying the reviewed pins in the root checkout. It
   validates clean-origin inputs, actual raw bodies/data/TLS/init, formal adapter
   and pure atomic/MemFS/lifetime transforms without hand-editing generated output.
5. Run the13 focused pytest suites listed in prepared-product.yml, including the
   complete19 binding mutation cases; run canonical inventory and public-source
   checks. Source CI already ran unchanged Go protocol/guest race packages on
   both OSes; this binding-only follow-up does not claim another Go runtime run.
6. Push the exact candidate to experiment/prepared-product. CI rebuilds a fresh
   exact-source guest, formally installs/compiles it and runs both-OS runtime
   gates including25 LONG_DATA native comparisons. Stop after submitting CI.

The converter's420 source files exactly match the previously preserved complete
reconstruction inventory (including go.mod); see [cleanup proof](cleanup-source-proof.json).
Preserve synthetic test Git history before removing scratch. Delete converter,
raw generated/adapter trees, archives, venv/caches and completed clean worktrees
only after saving compact evidence and reproducible-input records.

LONG_DATA runtime acceptance and executing-query cancellation/disconnect plus
remaining resource/failure paths are still P4 work. P5/P6 and final canonical/J1
acceptance remain separate unfinished work; no scope reduction is implied.
