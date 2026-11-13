# Buffer-pool zeroing spike (UNQUALIFIED)

Product baseline: eb175ae23292c1c40cfbeb4b9b73132873c4cc6f,
guest 5f8b711f8efe31529c12847a093e92b8f962598e035cb1d5e253e41093feee20.
Authorization: Human requested implementing the bounded experiment after
ac381f6d's source-contract investigation. This is not product adoption.

One experimental C guest contains baseline/metadata/poison/bad-descriptors
modes. Its default is baseline. The mode is supplied only through the explicitly
named internal experiment variable; normal per-instance environment remains
otherwise unchanged. `guest/experimental.patch` changes only buffer-pool create.
The common zero-filled allocation helper and release inputs are unchanged.

Use the existing exact canonical CI guest/native generated source as the
canonical control. Build one fresh experimental guest with pinned LLVM23,
Binaryen133 and sysroot; verify source and mode witness identities. Compare
baseline vs metadata within that same guest to control translation/layout
changes, and retain the canonical guest comparison as an external anchor.
Poison fills the pool with 0xa5, clears descriptors, verifies every frame byte
and descriptors before use, and records counts/alignment. Bad-descriptors
intentionally omits descriptor clearing and must fail its explicit check.
Poison and negative control are correctness tools, never timing variants.

Run correctness before performance: root + repeated Snapshot/Fork isolation;
large InnoDB data beyond 16MiB and repeated reads/updates to force reuse;
ROW_FORMAT=COMPRESSED; shrink/partial-extent/regrow; startup/SQL error cleanup.
Reuse existing relevant actual-guest oracles for recovery and I/O failures where
available. Explicitly report any non-executable coverage; do not silently call
that product acceptance. Stop an optimization on correctness failure.

Then use matched modelcase inputs for fixed P1/P8, three rotated pairs of
baseline/metadata plus canonical controls, with warmups. Record Fork, SQL,
Close and complete lifecycle separately. No extra parameter sweep or default
capacity change. Preserve source/guest/binary identities and observations.

Dedicated workspace budget20GiB, min-free8GiB; C build timeout2700s, native
regeneration2700s, bounded measurement1800s. Delete recreatable state after
preserving report, source patches, compact results and hashes. Failure still
requires evidence preservation and cleanup. Main integration/release are
separate decisions.
