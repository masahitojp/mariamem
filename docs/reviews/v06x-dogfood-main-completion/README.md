# PR3 protected main adoption completion

The Human-approved bounded dogfood candidate was adopted through
[PR3](https://github.com/masahitojp/mariamem/pull/3), with no admin bypass or
protection edit. The prior [decision](../v06x-dogfood-main-adoption.md) owns scope
and accepted limitations. This receipt records completion, not release approval.

| Identity | Source commit / tree |
| --- | --- |
| Starting main base | `250bceb80be4cfc9f7c844d888af864fc1d38d25` |
| Reviewed code candidate | `d389306f9ae0514824f79fccbe2800776786a7ac` |
| Final checked PR head, documentation/evidence additions only | `0490b43a21dceeab10b33d94b5b92bf383e4055e` |
| Actual final PR CI merge source | `730bd17c935928dd37e2cd7df14aa115c40e89a7` |
| Actual main squash/adoption source | `ebb97260788710b2065e81481b2c2f516d6f7e52` |
| Shared tree of final head, actual CI source and main squash | `c98a74c854d59cf19f1584a7cb5fa994e0f6632b` |

[PR before](pr-before.json) fixes checked head/base and the synthetic CI merge
commit before integration. [PR after](pr-after.json) records merged=true and
merged_at2026-10-27T13:36:39Z; [main ref](main-ref.json) independently confirms the
squash identity. [CI commit](ci-commit.json) and local Git object inspection
confirm the shared tree and commit parents. Old receipts retain their original
tested sources rather than being renamed to the squash SHA.

[Check-runs](check-runs.json) records all20 completed/successful checks attached
by GitHub to the PR head. Check attachment is distinct from GITHUB_SHA/checkout
provenance: the completed Live log confirms actual source730bd17 and artifact
names also retain that merge SHA. The raw completed log is retained under the
coordinator's ignored build receipts; [selected log observations](log-observations.json)
record source and cache restoration without republishing developer paths.

Completed final CI runs:

- [Development40502167065](https://github.com/masahitojp/mariamem/actions/runs/40502167065):
  check/integration succeeded.
- [Django40502166621](https://github.com/masahitojp/mariamem/actions/runs/40502166621):
  native2 and both-host/minor guest4 succeeded.
- [Live40502166546](https://github.com/masahitojp/mariamem/actions/runs/40502166546):
  references, both hosts and required aggregate succeeded.
- [Dump regression40502166708](https://github.com/masahitojp/mariamem/actions/runs/40502166708):
  all compatibility/regression jobs succeeded; no new dump claim is made.

[Post-merge protection](protection-after.json) confirms required check,
integration and Live required gate, all bound to GitHub Actions app15368,
strict=true and administrator enforcement. No intervening policy change was
observed. The normal merge matched exact head0490b43; no force/admin flag or
direct main push was used.

The native references and both Live host jobs restored their compiler caches.
The host job elapsed observations are macOS35m31s→9m02s and Ubuntu19m11s→8m19s
between runs40492426087 and40502166546. They exclude waiting for a runner/job
dependency and are different-run observations, not a controlled cache-only
benchmark or an end-to-end PR latency claim. Main now has the reviewed CI reuse
behavior; no further runtime change is inferred from those times.

Manual parallel guide execution, required Django check policy, actual guide-only
skip/model acceptance, docs/reviews allowlist and broader Go/native interruption
coverage retain their previously stated scope. Qualification, version and
publication were not started. These completion edits are documentation/evidence
only and do not alter the adopted code or protection.
