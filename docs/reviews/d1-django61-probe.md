# D1 on latest Django: bounded compatibility probe (2026-11-03)

Conclusion: the unchanged D1 implementation passed all existing serial20 and
parallel15 expected scenario assessments on Python3.14.10 + Django6.1.2,
macOS27.2 arm64. No compatibility failure was found in this fixed workload.
The5.2-only dependency bound records the previously qualified profile; this
probe finds no runtime reason to retain that bound for6.1.2.

Recommend a small support follow-up to qualify latest Django and widen the
installation contract. This probe alone does not adopt a new supported range.
The remaining objection is opposite-platform coverage and the distinction
between executing the adapter and installing its declared extras normally.

## Exact scope and evidence

- Test recipe source_commit: `aa6b1b4cc74455d4ea7d512772bde414fb7565e9`, clean.
- Installed candidate source_commit: `d99f07cd16a8a11c1644225206a3d1fcc0a39edd`,
  reused from Release41457221670. Wheel hash and embedded host VCS identity were
  verified before execution; every Django adapter Python file matched the recipe.
- The isolated environment changed only Django5.2.8 to6.1.2 in the existing pinned
  requirements. Candidate wheel was installed with --no-deps to avoid invoking
  its5.2-only extra. This is a compatibility probe, not a normal supported install.
- Existing serial campaign:10 manage.py and10 pytest scenarios. Existing parallel
  campaign:15 scenarios, including2/4 workers, load/loadscope, negative restoration,
  real SIGKILL/restart, cleanup-debt and no-acquisition/refusal controls.
- Every aggregate and expected scenario assessment passed. Intentional failures
  retain their failures; parent PASS means the expected detector fired.
- Detailed identity, package versions, aggregate hashes and host-exit count are
  retained in [the compact summary](d1-django61-probe.json). Raw local logs remain
  in the experiment workspace evidence, not in this Git diff.

[Official download page](https://www.djangoproject.com/download/) identified6.1.2
as latest stable at the time of the probe. Source code, extras, CI and published
version were not changed. No Release CI, runtime build or performance run was
started. Ubuntu, Python3.12/3.13, Django6.0 and arbitrary application suites were
not tested; no claim covers all6.x releases.

## Reproduction and next step

Create an isolated Python3.14 environment. Install the existing
`tests/django_lifecycle/requirements.txt` with its Django line replaced by
`Django==6.1.2`, then the identity-checked candidate wheel with `--no-deps`.
From the clean recipe checkout, run:

```sh
python tests/django_prepared/run.py --installed --host HOST --host-source-commit d99f07cd16a8a11c1644225206a3d1fcc0a39edd --output SERIAL_OUTPUT
python tests/django_prepared/xdist/run.py --installed --host HOST --host-source-commit d99f07cd16a8a11c1644225206a3d1fcc0a39edd --output PARALLEL_OUTPUT
```

Before claiming support, update extras/docs and qualify the declared range on
both supported OSes. Prefer representative LTS/latest cells in the existing
Django job over multiplying every version combination. Any intermediate version
admitted by a widened bound needs an explicit coverage decision as well.
