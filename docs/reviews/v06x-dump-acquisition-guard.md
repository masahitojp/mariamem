# Accepted acquisition evidence and Linux guard follow-up

2026-10-25. The Human accepted the
[native acquisition evidence](v06x-dump-acquisition-review.md) **for the observed
hosts only** (macOS27.0.1 arm64; Ubuntu24.04 x86_64). The acceptance does not
establish a reusable gate, setup cost or dump import. The historical review and
its original receipts remain unchanged.

The requested next change is confined to Linux native acquisition assertions.
No dump comparison, cold Mac exercise, setup-cost measurement, main integration,
Qualification or release is resumed by this work. A later cold-install claim
requires a separate clean-machine run and separate warm/cold observations.

## Exact changed object

- Base source_commit: `6d81a2f99d0b5bd09bb5ab48dbf1ae23ca27e149`.
- Candidate source_commit: `f94a2d4895a838faca3e3bfcafa3aa4ce3a18033`.
- Branch: `experiment/dump-import`.
- Four changed files: the acquisition workflow, native pin JSON, collection/
  assertion helper and its identity mutation tests. Product/runtime/SDK/guest/
  converter/generated inputs are unchanged.

The new
[helper](https://github.com/masahitojp/mariamem/blob/f94a2d4895a838faca3e3bfcafa3aa4ce3a18033/tests/dump_import_spike/linux_acquisition.py)
checks each of mariadbd, mariadb and mariadb-dump independently. It resolves the
selected executable path, hashes the actual bytes, reads ELF class/byte order/
machine from each binary, and compares the complete version output against the
[pinned observed identities](https://github.com/masahitojp/mariamem/blob/f94a2d4895a838faca3e3bfcafa3aa4ce3a18033/tests/dump_import_spike/linux-native-pin.json).
There is no substring version match or substitution of uname for binary identity.

The helper also binds the running container's image ID to the exact linux/amd64
manifest/config ID, verifies host Linux/x86_64 and exact startup-query output,
and uses `scripts/git_identity.py` to require a commit object, exact checkout
equality to the requested GitHub SHA and a clean tree before and after collection.
`GITHUB_SHA` is passed explicitly by the
[workflow](https://github.com/masahitojp/mariamem/blob/f94a2d4895a838faca3e3bfcafa3aa4ce3a18033/.github/workflows/dump-import-spike.yml).
Checks use explicit exceptions so Python optimization cannot disable them.
PASS is emitted only after all checks; failures emit FAIL and a nonzero exit.

The workflow's later canonical-input/producer job has been removed. Pushes of
guard, pin, test, source-identity or workflow changes trigger acquisition only.
The earlier producer source/history remains preserved; removing its automatic
job does not start or discard an additional dump experiment.

## Verification and handoff limits

Local verification passed:

- Six unittest methods, including per-program version/path/hash/architecture,
  program inventory, source commit/tag/abbreviation, host/image/startup and ELF
  header mutations. The same tests also passed under `python3 -O`.
- Touched Python syntax checks; YAML parsing and workflow structure checks for
  acquisition-only jobs and explicit GitHub source-SHA wiring.
- Public-source boundary check (5250 files on the experiment candidate), plus
  diff formatting. No runtime acceptance or broad release check was run.

These are local code/negative-control results, not a native execution PASS for
f94a2d4. The strengthened acquisition workflow is the next CI submission; its
run URL is returned in the handoff. The old CI40169643384 receipt remains bound
to d19ab2e and is not relabelled. Do not reuse the old workflow as an automatic
input gate; any later gate receipt must come from the asserted exact-source
workflow and preserve these host/scope limits. Even a new acquisition PASS does
not authorize the stopped dump comparison or prove setup cost/import behavior.
