# Reproduce the routine bootstrap candidate

Use the final `experiment/routine-bootstrap` candidate in a clean disposable
experiment workspace; read its implementation report for actual source SHAs.
The successful local guest source is dd6438a6da76ef9ed85ceb47d861d24112330b84;
ordinary host generation/testing is 1e2834c20baa0c3596d6cb32e61f137b11d52dc5.
Later docs/tests/CI edits do not make those the same SHA. The final CI uses a
fresh guest build from its own exact SHA. Do not bypass source-origin rejection
to reuse an old receipt across changed workflow/build inputs.

1. Use `.github/workflows/routine-bootstrap.yml` for the portable Linux arm64
   source builder: pinned Ubuntu base, declared apt dependencies, then
   `scripts/build_generated_guest.py --development-output <absolute-output>`
   as root on a fresh Linux arm64 SDK/work directory. Local runs used Docker
   builder image sha256:3ded805d8dcae3ffdf39515c3f0540b27b695719570903594452f8787abe570f;
   `guest-build-c.sh` is the actual retained mount recipe. Create its empty
   linux-root-c/linux-work-c/builder-build-c directories and seed the last one's
   go.mod from tracked build/go.mod. Fixed SDK archives are checksum verified;
   the guest record records actual host tools/options too. Budget32GiB, reserve
   free16GiB; use Python3.14 for the local disk guard.
2. In a clean native checkout with Python3.14, PyMySQL1.2.3, pytest8.4.2 and
   Go1.26.8, run the normal route, with an absolute, nonexistent output directory:

   ```sh
   python scripts/regenerate_release_guest.py --development \
     --guest-dir /absolute/fresh-guest --output /absolute/native-a
   ```

   For owned task caches unset inherited GOPATH/GOCACHE/GOMODCACHE before selecting
   MARIAMEM_DEV_WORKSPACE. See the experiment-workspace guide; avoid global caches.
   This builds the exact13-patch converter, installs through generate_runtime.py,
   compiles a new host and runs the standard SQL/Snapshot smoke. It is UNQUALIFIED.
   Use the produced product/python and native-a/mariamem-dev-host, not the root
   checkout's unchanged canonical transpiled guest.
3. Run tests/test_routine_schema.py, tests/test_dev_guest_tools.py and
   tests/test_thread_lifetime_binding.py (55 local cases). Set PYTHONPATH to the
   generated product/python and MARIAMEM_ROUTINE_HOST to its binary, then run
   tests/test_routine_bootstrap_runtime.py. MARIAMEM_ROUTINE_EVIDENCE selects raw
   output. CI installs Connector/Python26.7.0 and requires its test via
   MARIAMEM_ROUTINE_REQUIRE_CONNECTOR=1; unsupported local OpenSSL4 is an explicit
   SKIP, never a substitute Connector PASS. The J1 test invokes the existing
   fixture adapter and preserves the negative exit1/control assertions.
4. Inside the generated product run Go tests for the per-instance environment
   and mysqlwire; run tests/v06_routine_probe, tests/v06_prepared_probe and
   cmd/mariamem-guest auth-check. Use -p1/-trimpath and separate evidence outputs.
   See acceptance-commands.json for exact actual arguments and returns.
5. Independently repeat step2 in another empty output. Compare all52 raw-module
   files. Then run scripts/generate_runtime.py independently with the first
   source-module and its same installation-inputs.json into a new empty output;
   compare every byte of all99 installed files, including provenance. Do not
   normalize or omit path-derived provenance to assert equality.
6. Optional cost diagnosis: copy tests/v06_routine_timing into the generated
   product's tests directory. Run its prepare_overlay.py from the source
   checkout with --product and a fresh --output. Build that test program with
   go build -overlay=<output>/overlay.json; run it to save guest-timing.json.
   The pinned handwritten-owner preimage must match. This **separate diagnostic
   binary** only copies a timing file after execution ends. Do not apply it to
   product source or treat it as the candidate binary; assert the99-file
   candidate inventory is unchanged. For ordinary API times use cost_probe.py
   with product/python, the normal candidate host, and a fresh timing directory.
   Those public traces have no guest subphase payload: the timing file is not
   part of ordinary DB-data export. Keep this observation gap explicit.

Expected fixed guest SHA256:
118ef83ee066d57f946603f7e2a2b2c60d9b5f1cd4d627c3d18a73cbd963350c.
No generated Go editing, patch/guard weakening, main integration, version bump,
Qualification, tag or publication is part of this recipe.

The first rejected guest25df44f5 is historical failure evidence, not an accepted
alternative input. Its real Fresh SQL4081 failure/cleanup is reproducible from
f599a4734e511b85a0aa68e6953fe98e9cec4a61 with host5ef394f (use git_identity.py
to resolve the latter commit). The fixed SQL/native/section-comparison records
explain its resolution. fresh_failure_probe.go.txt records the actual cleanup
probe; a normal library-API collector's missing timing-file failure is separately
retained and is not a failed routine feature test.
