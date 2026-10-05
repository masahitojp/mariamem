# Checked mmap integration experiment

Base: released v0.4.1 `547fb1a6c01e5edb0daa27de273a2e94e66eb098`.
First commit: memory semantics candidate `56be628bf2d976048c5ea6d1949879781ed75342`.
Second boundary: mmap spike `b9975c3ae33848442704007ad2647bd76e52a602`, cleaned
into per-owner allocation/grow/release on macOS arm64 and Linux amd64.
This is an isolated experiment, not a merge/release approval.

The released pure memory32 guarantee is unchanged from the checked candidate.
The two converter patches remain independent. `linear-memory-owner.patch` adds
one shared grow preparation callback; it does not change generated access sites.
An anonymous PROT_NONE range reserves the maximum. Initial/grown prefixes become
RW before logical MemSize publication. No relocation, eager clearing, custom
pager, CoW, forced GC or function/address patches. Virtual RW is neither physical
commit guarantee nor RSS. OS page size must divide the WASM page size.

The execution owner releases only after worker join and Snapshot export, including
panics. A non-cooperative worker still prevents safe reclamation. No hard-kill
or full-guest race-clean guarantee is made. Unmap errors are returned, with mapping
counters retained; successful release is never fabricated. Go memory limits do
not account for this external memory: use the OS/resource guard.

Use pinned `scripts/experiment_workspace.py` from tooling commit `d492e52`:
prepare an owned workspace with free reserve 16 GiB / disk budget 6 GiB, then run
these scripts under its `run --timeout` command. Shared Go/toolchain caches stay
outside scratch. `support.py` applies additional RSS 6 GiB / physical-or-PSS
8 GiB, CPU180/200s, FD256 and individual timeouts.

- `prepare.py`: pinned converter, canonical source regeneration, heap fixtures.
- `accept.py`: identical fixtures on mmap; real guest grow/worker/ownership and
  SQL/session/Snapshot/Fork checks, focused runtime races.
- `products.py`: private installed platform wheel, SQLAlchemy, local GORM and
  supported failure/reconnect cases. No published artifact is changed.
- `measure.py`: three identical-source probes, balanced fresh trials, 1×20,
  mmap1×50, 4×12 (stop bounded heap controls on resource limit), Fork1×20.
- `prove.py`: positive retained-symbol attribution, provenance, canonical check
  and independent regeneration.
- `ci.py`: Ubuntu24.04 actual execution, not cross-compilation.

Paths are supplied through `MARIAMEM_TOOLING_REPO`, `MARIAMEM_CACHE`,
`MARIAMEM_RELEASE_GUEST`, `MARIAMEM_PREPARED_TEMP` and
`MARIAMEM_PRODUCT_TEMP`. Optional Python interpreters are
`MARIAMEM_TEST_PYTHON` and `MARIAMEM_CHECK_PYTHON`.
The modified existing Ubuntu workflow is experiment-only, verifies the exact
pushed SHA and retains compact evidence without release/tag publication.
