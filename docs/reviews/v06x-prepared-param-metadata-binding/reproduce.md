# P4 parameter-metadata guest: exact binding, runtime gate next

[Source CI39724676227](https://github.com/masahitojp/mariamem/actions/runs/39724676227)
completed successfully at source_commit
`ab8c3503f35e6ded515e2e0c58efc508099f6baf`. Guest-source119645765553,
macOS unit119645765309 and Ubuntu unit119645765602 PASS. Development-runtime
119648289370 SKIPs intentionally on the source-repair branch. In particular,
this verifies compilation of the embedded C++ extension, not native metadata
parity or LONG_DATA runtime acceptance.

The [verified complete guest receipt](guest.json) records clean tracked-source
identity, all source/overlay/toolchain inputs and linked/optimized Wasm hashes.
New optimized guest SHA256:
`8f6177627855232d096cfb3987d94e35c19fc4fc0c7f32ca8c69ff9fd4990a40`
(18,405,460 bytes). It remains a development UNQUALIFIED guest.

## Offline binding review

[Translation inputs](translation-inputs.json) and [raw inventory comparison](raw-inventory-comparison.json)
retain the same converter730057c, archive1adc74bb, darwin/arm64 binary430bf085 and
all13 canonical patches. All420 patched converter source files also equal the
previous independently reconstructed inventory: [cleanup proof](cleanup-source-proof.json).
This is one verified translation, not independent canonical regeneration.

Complete diffs and [layout review](layout-review.json) establish the following
limited relation to prior LONG_DATA guest f5ce001d:

- Fn131 is byte-identical. Fn153 changes48 literal occurrences, Fn214 changes62;
  each changed address is in the same relative BSS position shifted by64 bytes.
  All other numeric literals, object/argument-relative offsets and nonnumeric
  source structure are unchanged. Every observed address pair is enumerated.
- The full Fn67 initialization changes only seven enumerated length/address
  occurrences. Segment0 grows64 bytes to6,213,094 and still starts at8,388,608.
  Segment1 retains642,620 bytes at14,601,728. TLS moves to15,244,352, retaining
  exactly505 bytes and SHA25611982067. BSS moves15,244,800→15,244,864 with
 8,982,576 zero-filled bytes; the initialization guard moves24,227,376→24,227,440.
  Inter-segment/TLS/BSS padding remains26/4/7 bytes.
- Full data.bin and segment0/1 identities change; their contents are explicitly
  repinned. Equality of those contents or whole-runtime behavior is not claimed.
- This numeric comparison is an offline review of one observed layout. The
  installer still matches the exact complete function hashes and one exact
  guest hash. It does not accept address normalization or arbitrary relocations.
  The entire memory initializer is pinned too. Mutation addresses use the new
  literals; the prior f5ce001d guest is explicitly rejected alongside all older
  staged identities.

The formal source-only adapter and pure atomic/MemFS/lifetime owner transforms
[PASS](owner-checks.json). Local122 focused Python/C checks PASS, including
normal/ASan/UBSan ownership, strict parameter-alias mismatch control and20 binding
mutation cases. Canonical inventory PASS concerns the unchanged old canonical
runtime. Source CI ran the unchanged three Go race packages on both OSes before
this binding-only follow-up. The new guest has not been compiled/executed as Go
locally; actual runtime verification remains the next CI gate.

## Reproduce and continue

Follow the [prior binding recipe](../v06x-prepared-long-data-binding/reproduce.md)
with clean source_commit ab8c350 and matching39724676227 guest/unit artifacts.
Keep the origin worktree clean throughout verify_guest; do not expand origin
exceptions when root's owner pins change. Use a24GiB workspace budget,8GiB free
floor, Python3.14 and actual Go1.26.8 on PATH.

Copy translate.py, inspect_fast.py, layout_review.py and check_owner.py from this
folder into workspace/temp. Put complete downloaded artifacts in temp/ci and the
fixed converter archive in temp/wasm2go.tar.gz. **Wait for artifact download to
finish before copying**: an initial attempt stopped at missing-guest discovery
before any translation; it produced no verification result and was restarted.
Run translate.py with its absolute path through experiment_workspace.py run.
Inspect all full-body/data/init differences before updating root fixtures/pins;
run check_owner.py afterward. The layout helper additionally verifies that every
changed function address preserves its BSS-relative offset and length.

Run the13 focused pytest suites in prepared-product.yml, canonical inventory,
public-source and diff checks. Preserve compact evidence and verified synthetic
test Git history; remove archives, converter Git metadata only after complete
source-inventory proof, generated/adapter copies, caches/venv and clean worktrees.
Path substitutions in local logs are separately hashed in log-storage.json.

Push the exact new candidate to experiment/prepared-product. CI must rebuild its
own matching clean-source guest, formally generate/install/compile it, and run
both-OS smoke, exact binding/20 mutations, all previous P1/P2/P3/lifetime controls
and all25 LONG_DATA comparisons against the unchanged native packets. Source
success and offline binding are not a fix-success verdict. Stop after submission.

The original [metadata defect](../v06x-prepared-param-metadata.md) stays open until
that strict runtime comparison PASS. Remaining executing-query cancellation/
disconnect/resource/failure paths still belong to P4, followed by P5/P6 and final
canonical/J1 acceptance. No scope reduction, main adoption, Qualification or release.
