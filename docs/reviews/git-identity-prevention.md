# Git source identity — recurrence prevention

The earlier product audit explicitly identified `dd84ca4…` as a tag object.
Release publication and release-candidate resolution already peeled tags and
checked commits. The new comparison harness duplicated identity handling and
hand-copied that tag object into a source-commit constant. Its exact-commit guard
caught the error only after correctness/build work.

This follow-up addresses input acquisition and validation, not MariaDB behavior:

- Shared `scripts/git_identity.py` describes object SHA, object type and source
  commit separately; exact candidate gates reject annotated tag objects.
- `release/baselines/v0.4.3.json` is the single machine-readable baseline pin.
  Tag object, release name and source commit are verified together.
- Workflow preflight runs before tool setup/build. Direct runner invocation
  checks the same pin before scratch creation/build; the late duplicate guard
  is removed. Metadata uses `baseline_commit_sha` / `baseline_tag_object_sha`.
- AGENTS and development guidance direct future tools/agents to the shared path,
  rather than copying a raw `ls-remote` value. Existing correct publication
  mechanics remain unchanged.

Verification is bounded to real-Git object tests, runner fail-fast/gate/reducer
tests, Python/workflow syntax, affected public-source checks and wording/diffs.
It includes annotated/lightweight tags, commit/blob/tree input, reversed/duplicate
fields, different target commit, wrong release name, bad schema, and failure
before build/scratch. No runtime acceptance or benchmark campaign is required.

Local results: **10 real-Git tests + 6 harness tests PASS**. Actual published
v0.4.3 pin verification, Python/workflow syntax, public-source boundary (661
files), version consistency and clean diff checks pass. Temporary test repos
are self-cleaning; completion preserves only reports/identity JSON/Git history.

This branch derives from candidate `c5f43106a8054bb59a2da9184a1c2103fe1a1d9f`.
It is `experiment/v044-git-identity-guard`, kept separate so the already-submitted
v0.4.4 qualification is not restarted by a tooling-only change. No main merge or
release occurs. Its exact-source platform qualification is not claimed; folding
it into a release candidate requires that candidate's normal qualification.
