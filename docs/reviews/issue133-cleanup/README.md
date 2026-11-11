# Issue133 evidence and workspace audit — 2026-11-11

This audit preserves the completed experiments and removes disposable checkouts;
it does not adopt/reject a wire candidate or start another engine build.
The original 22-item C2 inventory and six historical normalization results remain
at commit `c24cbb6ec2063088cf2edd08eb9358ecb0579f19` under
`benchmarks/spikes/issue65-evidence-cleanup/`. That inventory describes a historical
native candidate, not requirements for current main.

## Evidence preserved and checked

- `source-pins.json`: all47 cited Git source hashes independently rechecked.
- The historical `normalize.py` rechecked all6 raw hashes/path-only recipes and
  normalized hashes. Historical FAIL/PASS values were not rewritten.
- `remote-reachability.json`: cited source and retained candidate commits are
  ancestors of advertised remote heads. This checks Git identities/reachability;
  it is not a fresh clone or proof of binary artifact availability.
- `dependency-disposition.json`: all22 historical inputs classified. Tracked
  source is saved, downloads/toolchains have pinned recipes, generated bundles
  and operational environment are not declared freshly reproduced.
- CI42801293564's complete development receipt, source identity, prepared result,
  CALL/metadata observations and host output are saved here. Only its CI host
  directory prefix is normalized; `ci-normalization.json` retains original and
  normalized SHA256 and replacement counts. The original small raw evidence is
  kept under root `build/issue133-retained/ci42801293564` for exact-byte inspection;
  that archive is evidence, not a runtime or build input.
- `historical-maintenance-map.py`: previously ignored unique helper preserved
  in full. Its small lifecycle records are kept under root
  `build/issue133-retained/issue131-source`. They do not define a product input.

The archived root `issue65-issue-update` files are unique before/after Issue
history, not build scratch; preserve them. Existing compact helper evidence
folders are retained with their original receipts. Local phase logs are not
substitutes for source or runtime acceptance.

## Scope and ownership

Six Orca worktrees were inspected, including ignored files and exact remote refs.
All were clean. Five had no observed process cwd; their ignored helper evidence
was exported and the clean checkouts were removed without force. The upgrade-trial workspace
still has an attached shell/Codex session and is protected pending owner input.
`worktree-disposition.json` records the before sizes and final actions.

The main working tree has pre-existing modified documentation/tooling and
untracked design/review files. They remain untouched. The issue123/uca worktrees
and unrelated root Live/scope tasks are outside this cleanup. No branch/ref is
deleted and no active process is stopped. Missing worktree registrations need
no disk recovery and are not used as a reason to prune unrelated metadata.

## Reproduction and remaining conditions

Current preparation is now maintained in main by PR151 (`584004b2`): clean
source preparation for current12.3.3 and historical13.0.2 legacy was compared
against independent producers. Those product inputs do not require these Orca
checkouts, old ignored folders or old native C2 bundles.

The older native C2 complete guest/translation/binary/wheel chain remains
unreplayed; the old inventory explicitly identifies missing raw receipts and
operational assumptions. Preserving source and summary hashes does not close
those conditions. If that candidate is selected later, final clean generation
and public acceptance belong to its authorized #134/#132 work, not a cleanup
build. Partial raw-row CI used an expiring previous-run guest artifact; its
source/identity and results are saved, but the temporary CI workflow is not a
permanent regeneration path.

Issue133 should remain open for the protected active workspace and the
candidate-dependent final reproduction audit. This bounded audit does not close
#65, resume#138, waive a contract or claim all original artifacts are available.
No runtime code/tests/build, benchmark or CI was run. Only source/evidence/hash,
public-source and workspace/ref checks were performed.

## Final cleanup result

Five clean, inactive Orca checkouts removed: 1,880,916 KiB (about1.79GiB) of
allocated checkout space. Branch refs remain remotely available. The attached
upgrade-trial retains429,340 KiB (about419MiB). Original small raw evidence retains
3,000 KiB; normalized complete CI evidence is on this pushed report branch.
No individual audited Issue65 workspace remains above1GiB. The broader root
helper aggregate remains about1.90GiB across compact evidence and unrelated
Live/scope/performance work; this is explicitly not a global disk-cleanup claim.
The scoped native-live helper action only finalized metadata, growing the root
aggregate by4096 bytes; no recovery is credited to it.

`cleanup-result.json` and `worktree-disposition.json` record the accounting.
Protected root modified-file fingerprints were checked unchanged. The owner
question about the remaining attached session is pending. Source/runtime
acceptance is not inferred from deletion or Git reachability.
