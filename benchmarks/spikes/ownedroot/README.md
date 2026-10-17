# Guest-disconnected owned-root component spike

Experimental source only. Nothing imports this package from the product runtime.
Approved scope: ownership/content oracles, per-route payload counters, lifecycle,
and digest-bearing handoff design. See `docs/reviews/snapshot-ownership-contracts.md`.

`Builder` and `Owner` use the same sparse-block/file reader. Freeze seals the root
and records metadata identities; Acquire checks that exact root/request and its
metadata. Old writer handles reject changes. Fork copies metadata and references
immutable blocks; its first write copies only the inherited valid block prefix.
There is no parent-root chain. Counters and metadata copies are diagnostic costs,
not a proposed final runtime layout or a timing benchmark.

The bytes of blocks never leave through the API; WriteAt copies input. Mutable
handles are revoked by their builder state. Package-internal corruption remains
possible and has an explicit characterization test: no-hash Acquire does not
detect a direct byte mutation, whereas the independent strict oracle does.
This difference is not accepted as a product contract change by passing tests.

Counters record helper-level bytes, not CPU instructions or physical memory-bus
traffic. Copy counts its source read; hashing counts reading its buffer; zero-fill
is separate from a source read. The payload helper call sites are small enough
to inspect. Application and strict-oracle reads are outside Freeze/Acquire.
Mapped import uses an actual OS mapping in the platform fixture, copies to heap,
and verifies independently supplied expected content before unmap. Handoff is
an in-memory serialization adapter with the current manifest JSON schema; it is
not the production FD/path/IPC transport. Those integration paths are untested.

Reproduce on Go1.26.8 macOS arm64, from a clean committed experiment source:

```sh
python3 scripts/git_identity.py inspect HEAD
python3 scripts/experiment_workspace.py prepare owned-root-replay \
  --branch experiment/snapshot-owned-root-spike --min-free-gib 20 --budget-gib 4
python3 scripts/experiment_workspace.py run --timeout 1500 owned-root-replay -- \
  python3 benchmarks/spikes/ownedroot/run.py --go /path/to/go1.26.8/bin/go
```

Run the prepare command outside any worktree already holding that branch.
The runner pins toolchain version, checks source identity, uses task-local caches,
saves every Go JSON event and records strict/base tests separately from the model.
CGO is disabled for ordinary checks and enabled only for `-race` as required by Go.
An instrumented heap/race PASS is not evidence that arbitrary mmap races are safe.

No MariaDB execution, user-workflow timing, independent Go generation, release
qualification or Ubuntu execution is included. Product/generated source is
unchanged. Production integration costs and API/manifest decisions are documented
in the result report, not silently hidden behind this component result.
