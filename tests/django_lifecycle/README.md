# Standard Django runner acceptance owner

This is the selected ordinary-settings portion of donor
`ac2cf6b5bc6b6e8a8066e5986f6000648523cb50`, on main base
`250bceb80be4cfc9f7c844d888af864fc1d38d25`. The original 13 app inputs in
`tests/e2e_native_control/pythonapp`, migration SEED, package pins, tests and
failure oracles are retained. `input-manifest.json` preserves the donor's original
metadata and explicitly distinguishes the new selection. Historical Fork
campaigns and their preparation script are excluded from this candidate.

`ci.py` owns the current executable campaign. `run.py` and `run_mixed.py` supply
oracles, not standalone campaign CLIs. The maintained
[workflow proposal](../../.github/workflows/django-lifecycle.yml) produces native
references first on Ubuntu, using the existing exact native acquisition guard.
Each guest platform/minor consumes only a matching reference and verifies its
host binary against the exact clean commit before starting mariamem.

```sh
# After linux_acquisition.py has accepted the native container into ACQUISITION:
python tests/django_lifecycle/ci.py --route native --native-port 3307 \
  --acquisition "$ACQUISITION" --expected-source-commit "$SOURCE_COMMIT" \
  --output "$NATIVE_REFERENCE"
# In the same source with the matching Python minor and pinned requirements:
PYTHONPATH="$PWD/python" python tests/django_lifecycle/ci.py --route guest \
  --host "$HOST_BINARY" --reference "$NATIVE_REFERENCE" \
  --expected-source-commit "$SOURCE_COMMIT" --output "$GUEST_OUTPUT"
```

Use fresh output paths. Local execution requires a bounded task-owned workspace
and exclusive resource authorization under the supervised run; do not start a
native or guest campaign merely to reproduce a pure test. The workflow bounds
native/guest commands with the existing disk/timeout guard and uses job-owned
Go caches. No browser or xdist workload is installed.

Per route/minor: 10 two-test lifecycle suites, eight mixed suites (six Django or
12 pytest tests each), plus one failed-migration suite for each runner. Each
mixed runner runs normal, reverse, shuffle137 and shuffle911+reverse. The guest
also executes the public recipe with each runner in normal and broken modes.
`observation.Runner` records around `super()` calls; pytest-django's DB fixtures
remain unchanged. `order_probe` permutes contiguous class/function groups only.

Default flush must yield an empty second-test application table. Serialized
rollback must restore migration SEED. Expected post-commit failure retains its
failure marker, exact process exit and successful second-test restoration.
Migration failure retains errno1146, the original ProgrammingError chain,
partial table and first two applied migration records, with zero admitted test
bodies. Each failed guest uses a fresh owner, then closes it without Snapshot or
reuse. A test-only probe checks source closure, process reaping and temporary
root removal; it does not force cleanup. Native parent cleanup removes only its
unique schemas after recording partial state.

Raw summaries/messages remain in each output. Comparisons exclude generated
schema names and host-specific traceback paths while retaining error types,
errno, failure identity, row/transaction/commit projections and cleanup. A PASS
assessment of deliberate failures is not a raw test PASS. Missing native input,
SKIP, missing case or different source blocks acceptance. Both supported guest
hosts and Python minors remain required before adoption claims.

Run the pure checks without server/framework dependencies:

```sh
python -m pytest tests/test_django_recipe_unit.py -q
```

See the [guide](../../docs/django-testing.md) for historical-source limits and
remaining unverified boundaries. None of the fresh native/runtime cells has yet
been executed for this candidate.
