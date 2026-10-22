# P2 binding reproduction and limits

Source build: [39554451701](https://github.com/masahitojp/mariamem/actions/runs/39554451701),
source_commit `00962f85fff7cdddadf8724c05f0f44834197b79`.
This is a single UNQUALIFIED source build, not independent source regeneration.

1. Download that run's `prepared-p1-unqualified-guest-00962f85fff7cdddadf8724c05f0f44834197b79` artifact.
   Verify `guest.json`, linked Wasm and guest with `dev_guest.verify_guest` in a
   clean checkout of the source commit. Use `scripts/git_identity.py inspect HEAD`.
2. Fetch the fixed converter archive recorded in receipt.json. With pinned
   Go1.26.8, run `benchmarks/spikes/generated-go-integration/translate_guest.py`
   with `--guest <mariamem.wasm> --guest-sha256 a52dd707d337d5349a7c5d72bc2108dc823cfe0c625742e93bc0875a2e3b519a
   --converter-archive <archive> --output <translation>`. Preserve/verify the
   complete input-manifest against translation-inputs.json using
   `dev_guest.verify_translation`. All13 patches remain unchanged.
3. Run the formal `setup_candidate.py --source-only` adapter before applying
   the atomic, MemFS and lifetime owners. The MemFS preimage belongs to adapted
   output, not raw converter output. install-owner-checks.json records only
   these pure transformations, not installation or runtime execution.
4. Compare the raw three function bodies with the checked-in P2 fixtures;
   function-comparison.json and Fn*.diff show the full P1/P2 change. Replacing
   only the observed +1152 literals for offline comparison leaves identical
   normalized bodies; runtime_thread_lifetime.py accepts only the exact new hash.
   Pin data.bin and segment ranges against identity.json. TLS505 bytes match;
   other data changes are listed in data-comparison/segment1-summary.json.
   Numeric ranges alone do not prove pointer/table/flag semantics.
5. Run `python -m pytest -q -rA tests/test_prepared_api.py tests/test_routine_schema.py
   tests/test_thread_lifetime_binding.py tests/test_dev_guest_tools.py` with
   Python3.14/pytest8.4.2. binding-tests.txt records50 PASS, including rejection
   of the previous P1 guest and independently mutated absolute addresses.
6. For actual installed output, the existing prepared-product workflow rebuilds
   at the exact new candidate, performs formal development generation and
   `tests/check_prepared_p1_binding.py --runtime <internal/generatedgo>`, then
   P1/P2 wire probes against unchanged native fixtures on macOS and Ubuntu.
   The historical check filename is retained; it now checks the P2 identity.

No source-origin allowlist is expanded to reuse the older guest with the changed
binding script. Actual execution, full J1 controls and P6 independent generation
remain pending. The raw translator's existing SSA/f16 diagnostics are retained in
translation.txt; no rewrite or guard was changed to silence them.

The first local attempt stopped before converter patches/build because inherited
GOPATH conflicted with workspace caches. The successful workspace removed those
inherited cache variables and used scoped caches. Logs scrub only local paths;
receipt.json records original/stored checksums. Disposable downloads, extracted
sources, generated outputs, caches and venv are removed after compact evidence
preservation. No user state is part of this cleanup.
