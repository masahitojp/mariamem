# Issue134: input resolver slice

Parent [#65](https://github.com/masahitojp/mariamem/issues/65) governs the goal:
reduce repeated MariaDB upgrade work. The Human authorized implementing the
bounded first slice after the concrete descriptor/migration review.

Base: published v0.6.2 source_commit
47121e1be0b399ba4e2270ce3e25c411ade0e2eb. Branch: experiment/issue134-input-resolver.
The unrelated parent checkout and its user changes are protected.

Deliverable: pure data resolver and three exact fixtures; no canonical command,
release input, preparation, SDK, generated runtime or public factory changes.
Input data comes from the pinned published/actual producer sources recorded in
the fixture registry. edc703fe727ff18aa2c2cefbcfff960d05c3a290 supplies the reviewed
profile-validation principles; historical pins stay historical, not relabelled.

Exit: three old input/lock objects reproduced; wrong selection, patch/stage
order or presence, corrupted patch/proof and unsafe paths rejected; no hidden
filesystem/network/process side effects. Results guide preparation integration,
not product adoption or a claim of net maintenance savings.

Verification budget: focused Python checks only, no heavy build/CI/runtime;
active ceiling2h including tooling30min. Owned source worktree target<600MiB,
free floor12GiB (start36GiB). Stop and report remaining work if exceeded.
Preserve useful source/evidence in Git, then remove owned worktree/scratch.

## Implementation and verification

`scripts/guest_input_resolver.py` exposes
`resolve_inputs(registry_bytes, engine, profile, read_bytes)`. It returns fresh
input/lock/stage/proof objects, descriptor identity and resolved-content digest.
It imports no repository common module and reads no ambient product selection.
All content arrives through the explicitly supplied byte reader. Future readers
own filesystem/symlink containment; the resolver validates relative path syntax.

The trusted registry pins descriptor and semantic output hashes. Valid metadata
cannot authorize changed blob bytes. It also checks engine/recipe identities,
patch file inventories and historical prepared pin/function-proof consistency.
Successful resolution proves input identity, not full prepared-source correctness.

Verification on macOS with Python3.14:

- 17 unittest methods PASS, including three independent expected input/lock
  vectors, both selection orders/no caller mutation, blocked ambient file/network/
  process operations, mixed selection, patch/stage omission/addition/order,
  patch/proof corruption, proof substitution, malformed JSON/schema and unsafe paths.
- All three golden objects and every patch/proof blob independently compared to
  the named Git source bytes; original input/lock byte hashes checked.
- Both touched Python files parse; public source guard passes; diff check passes.
- Tests load committed fixture bytes, so no historical Git checkout or local
  experimental directory is needed for execution.

The first local run rejected native's legitimate repeated patch-file sections.
The validator was corrected to preserve the existing complete file-set check
and exact patch digest, while allowing repeated sections within those exact
bytes. Final tests pass; no engine patch or original oracle was changed.

Run the focused suite with:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_guest_input_resolver.py -v
```

Existing canonical helpers and tests are byte-unchanged. No runtime, SQL, Go,
SDK build, benchmark, CI, release or network operation is part of this resolver.
The old preparation/build/verifier callers still use singleton inputs; see the
#134 migration map. Next is explicit-context preparation and actual full-source
comparison, then builder/public integration. Total maintenance benefit and
parent acceptance remain open. #138 remains stopped/unwaived.
