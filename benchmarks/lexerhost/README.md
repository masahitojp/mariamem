# Actual C guest host binding and acceptance

This is the next bounded experiment after [C input acquisition and offline binding inspection](../lexerbinding/README.md).
The Human authorized continuing on 2026-11-08. No actual C guest PASS is claimed
until the new both-host workflow completes. This is not an adoption, performance,
independent C reproducibility, Qualification or release gate.

## Immutable input and explicit host delta

Reuse CI [42433100335](https://github.com/masahitojp/mariamem/actions/runs/42433100335),
C source_commit `b1a265cc30a8603ced743c8aeb59c752751ff9d6`, guest SHA256
`14b41ceaec2b61d111eb749714cc1d6e40bb1fab503e8edc61abf76f16ab9fb1`.
`acquire.py` pins the guest/native-reference artifact IDs, ZIP digests and run.
It verifies bytes and rejects unsafe archive members before extraction. Artifacts
must still be available; expired/missing artifacts stop this route rather than
silently rebuilding or substituting another input.

`binding.json` freezes the 51-file raw translation inventory, full data hash,
three exact thread/reclaimer body hashes, exact CRC validator body/table offset,
canonical adapter source hashes and worker-layout hash. The profile itself is
hash pinned by `scripts/runtime_development_binding.py`. `worker-layout.json`
is a new fixed fixture, not a relabelled historical PASS. Its exact bodies and
integer changes were checked against the historical J1 oracle; one function's
partition moved (Fn219 from p3 to p7), without a function-name change.

Only `--development --development-binding lexer-prepared-c1` selects the new
binding. The canonical adapter modules, guest pins and generated runtime remain
unchanged. Separate module instances use the new exact constants while retaining
whole-body checks and the existing transforms. The canonical path still rejects
the new guest; the development path rejects wrong profile, origin, inventory,
body, guest or table inputs. The generated runtime stays outside the checkout.
The installer revalidates the profile and full translation before applying it.

The historical guest's source inventory is verified against its actual Git
commit. Reuse permits docs/tests, the named host regeneration files, this named
recipe, the recorded input receipt and workflow classification. Guest patches,
C producer, converter/build inputs and unknown host recipe files still require a
new C build. `development.json` keeps original C source identity and current host
source identity separately. This does not claim two independent C builds.

## Fixed acceptance campaign

The manual/push `lexer-host.yml` matrix is macOS15 arm64 / Ubuntu24.04 x86_64,
Go1.26.10 and Python3.14. It downloads the fixed artifacts, independently
translates the same guest, checks the frozen raw inventory and regenerates the
isolated host. No C rebuild occurs in this workflow.

1. Existing real-guest dev smoke: Fresh transaction commit/rollback, independent
   Snapshot children, Close and mapping cleanup.
2. Actual guest Go oracle: ambient verification switch ignored, profiling does
   not verify, all638 compiled descriptors compare all512 bytes, corrupted table
   is rejected. The existing exact oracle is added with a Go test overlay.
3. Actual guest worker-trap oracle: notification, peer isolation and disposal.
4. CRC differential/page controls against the exact original new validator. Only
   the test fixture's two concrete addresses change via exact numeric tokens in
   a Go overlay; production body transformation is unchanged. Both fixture hashes
   are recorded. Comparison/LSN negative controls remain in the offline suite.
5. Historical forced J1 ownership oracle with the new exact fixed layout:
   heap/mmap × unsafe expected failure / protected success / protected race.
   The failure assertions and completion ordering are retained.
6. SQL differential against the pinned native12.3.3 reference: literals,
   identifiers/comments, Unicode, binary/NUL and sql_mode; two children must each
   begin from pristine seed, commit their own change and retire connections.
   Cleanup asserts zero owners, reaped host, process exit0 and removed temp root.

`run.py` records each command status, host/C identities, profile/test hashes,
SQL/cleanup and full dev provenance. It rechecks source and installed runtime
inventories after the gates. Failed commands stop the campaign; no silent skip.
`SHA256SUMS.json` covers the receipt excluding the checksum file itself.
The source-bound CI artifacts are the next review input. Historical Go-surrogate
latencies are not measurements of this C guest. Performance is a later campaign,
and adoption/main integration remains a separate Human decision.

Local focused checks (no guest or compiler required):

```sh
python -m pytest -q tests/test_dev_guest_tools.py tests/test_lexer_host_binding.py \
  tests/test_generated_runtime_inventory.py tests/test_development_scope.py \
  tests/test_runtime_write_adapter.py
python -m unittest discover -s benchmarks/lexerbinding -p test_bindings.py -v
python scripts/check_public.py
```
