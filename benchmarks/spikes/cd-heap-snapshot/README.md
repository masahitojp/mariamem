# C versus D, same-process heap Snapshot

An isolated comparison on the same unchanged MariaDB 12.3.3 guest. Both modes
retain immutable Go heap state after guest shutdown; neither writes Snapshot
payload files, maps Snapshot files, or hands off FDs. C keeps contiguous files
and copies the retained logical file on first write/growth; D keeps 16 KiB
blocks and copies only partial-overwrite inherited blocks. C shrink is metadata
only; regrowth detaches and zeroes the truncated tail. Truncate-to-zero releases
a shared slice. Fresh C uses the existing MemFS contiguous growth policy.

Both keep three full logical content scans: source hash, target verify and owner
verify. Both use the same capture registry, guest join, lifecycle gates and Go
public workflow. This is not Python integration or persisted Snapshot support.
Current empty runtime management directories, sockets/pipes and Wasm memory
mappings still exist. Heap lifetime follows Go reachability/GC.

## Reproduce

Use an owned workspace of this branch, budget 12 GiB, minimum free 16 GiB.
Set GO_BIN and GOFMT to Go 1.26.8 absolute paths. Run git_identity.py inspect HEAD
before builds. Apply `instrument.py`; it checks canonical preimages against
main a8137b8b444f86068d3128a291e3a848adfdfd56 and records every output hash.
Run `build.py` under scripts/experiment_disk.py with a 1200-second limit.
Then run `campaign.py pilot`, `campaign.py verify`, `campaign.py measure`, each
under the guard (600 seconds is enough for this bounded campaign). Network
binding and fixed module downloads require sandbox permission.

Each mode/size gets 5 fresh-process plain timings, alternated C/D; resource
observations are 3 separate pairs. Small: 100 rows / 256-byte payload. Medium:
10,000 rows / 1024-byte payload. Migrate/seed users+orders, Snapshot, two sequential
independent children (CRUD, commit/rollback), close baseline. Final diagnostic
hash, scratch scans and resource sampling are outside timed whole. No timing
samples are discarded. Actual file bytes differ between independently seeded DBs.

Resource-only copy counters are cumulative process events. C-CoW records file,
phase and logical bytes copied; C-growth includes contiguous growth allocations.
D records dirty block allocation and source-prefix copies (including logical
zeros). These counters exclude ordinary SQL/driver/Go allocation; MemStats gives
the whole-process total separately. Counters do not run in plain timing.

Separate audit compares the captured state against the guest Export inventory
and bytes, all in memory. Boundaries exercise active transaction rejection,
parent Close with live children, derived baselines, concurrent independent SQL,
freeze failure and both full-content corruption checks. Run base tests with
-race separately; this is not a full guest race census.

Use summarize.py and reduce.py for compact evidence. Restore and replay overlay,
compare all postimage hashes to build-input.json, restore again. Only templates,
harness and evidence belong in the commit. Commit/push experiment, finalize and
clean owned workspace. No main integration or release.

See ../../../docs/reviews/cd-heap-snapshot.md for results and Human Review.
