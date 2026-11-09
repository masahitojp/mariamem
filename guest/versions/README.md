# Explicit preparation inputs (experimental)

The registry selects registered engine/profile descriptors. These feed the common
`prepare_guest.py` pipeline; no version switch overwrites the canonical input or
lock. Run `python3 scripts/prepare_guest.py --engine 13.2.0 --profile native-text
--work-dir <fresh-directory>` on an experiment branch. An optional
`--archive-cache <directory>` shares only checksum-checked archives; do not run
multiple writers against one cache. No SDK or compilation is performed.

Identical existing inputs are referenced directly. Different version/profile
bytes are kept under readable `inputs/` paths. Logical historical names inside
descriptors are retained for proof compatibility, including old spike labels;
the registry references maintained physical files here, never a local checkout.
A fresh private data-only input view adapts existing root-aware helpers. It does
not load executable code, change module globals, or rewrite product selection.

Corrected TIME and unchanged-file proofs follow edc703f. Original historical
producer fixtures remain unchanged in tests/fixtures/guest-input-resolver.
The recorded original commit is evidence provenance, not this new producer's
identity. Selected preparation uses a distinct receipt schema and remains
release-ineligible, including the stable engine comparison. Experimental native
classification survives physical relocation of its patch. The formal producer accepts selected inputs as described below; binding review
and public acceptance remain required.

13.2.0/native-text is now an explicit preview evaluation entry. Descriptor schema2
requires published-preview provenance and the checksum-bound published revision
file; it uses no invented annotated tag. Schema1 still requires distinct source
and tag objects. The official distribution was compared with all27,551 tracked
Git blobs at its embedded source revision. Its extra bundled dependencies are
not silently imported: preparation uses the exact commit archive and the shared
reviewed dependency lock. Neither the preview nor13.0.2 is the intended product
engine; the Human targets13.3 LTS. Existing stable input/lock remains12.3.3.

For a new preview descriptor, `origin` identifies the inherited input/patch
ancestry. It is not a13.2 producer claim; the actual preparing/building commit
is recorded separately in evidence and later producer receipts.


## Formal producer and binding handoff

On a fresh Linux arm64 builder, with a committed experiment branch and the pinned
build prerequisites, use the same formal builder with explicit evaluation input:

```sh
python3 scripts/build_generated_guest.py --engine 13.2.0 --profile native-text \
  --repetitions 2 --development-output /opt/mariamem-selected/guest
python3 scripts/regenerate_release_guest.py --development \
  --engine 13.2.0 --profile native-text --translation-only \
  --guest-dir /opt/mariamem-selected/guest --output /opt/mariamem-selected/review
```

The builder still requires root for its fixed SDK/build paths. Omitting selection
preserves the stable canonical route. A selected build always requires at least
two independent source builds and an external development output. Its
`selected-development-guest-v1` receipt binds the resolved input, effective lock,
patch/proof inventory, complete prepared-tree identity, producer commit/source
inventory, toolchain and matching linked/final WASM. Every trial uses fresh source
and compiler outputs. Selected verification requires the caller's expected engine
and profile; it rejects old receipts and fallback to a canonical guest.

Translation writes `binding-inputs.json` with `BINDING_REVIEW_REQUIRED`, the exact
guest/translation hashes and all generated sources. It does not install the new
guest or reuse old worker function numbers. Review complete worker bodies/TLS/ABI,
then connect the reviewed binding and public candidate. The selected receipt
cannot pass the legacy installation or release contract.

`Selected guest generation` CI calls `scripts/selected_guest_ci.py`: two source
builds (combined limit120min), raw translation (30min), combined owned storage
24GiB/free floor8GiB. SDK, source, downloads, Go caches and outputs are included.
These are run limits, not a duration estimate or a new local capacity setting.
The initial experiment-branch push submits this acquisition step. The fixed
#65 completion conditions still include binding/public validation on both product
OSes and the upgrade-cost judgment. CI handoff does not close those conditions.
The source-only unit fixtures test routing/refusal; actual compilation belongs to
this workflow. Retain the handoff artifact for that active follow-up (14days),
then reduce it to compact evidence and discard recreatable state.

## Next-version registration and cost record

1. Verify source_commit separately from tag_object_sha. For an untagged published
   preview, preserve the distribution/revision evidence required by schema2.
2. Add a descriptor referencing unchanged shared inputs; register its exact
   descriptor/input/lock/stage identities. Update full pre/postimages and
   profile/TIME/UCA/DDL proofs from actual source, retaining old descriptors.
3. Run resolver/proof negatives and actual preparation, then the selected formal
   producer above. Inspect resulting bodies before updating binding or public
   engine assertions; prior-version results are comparison evidence only.
4. Record edited files, manual decisions/review, automated checks and machine
   wait with the same required work. Separate one-time setup from recurring
   registration/proof/binding work and common from native-specific costs. Missing
   human-time observations remain unknown. Use the evidence to report improvement,
   regression or an inconclusive comparison before adoption; no cost-only rebuild.

## Selected binding and public source installation

Registered bindings live under `guest/bindings/`. Each entry pins the actual
producer, guest, both handoff receipts, the complete raw translation inventory,
three complete normalized worker bodies, TLS initialization and ABI/no-op facts.
A new version requires an explicit reviewed entry; function shape discovery is
never an installation oracle. Stable canonical worker binding remains separate.

Recreate the exact producer checkout from the registered `producer_source_commit`
with Git, download its existing CI artifact, verify the archive SHA, and extract
it to a fresh disposable directory. Then, from a clean committed installer tree:

```sh
python3 scripts/install_selected_guest.py --producer-root /absolute/producer \
  --handoff /absolute/handoff --engine 13.2.0 --profile native-text \
  --output /absolute/selected-install
```

Paths above are caller-owned disposable locations, not retained local inputs.
No historical checkout path or executable under an issue-specific spike is used.
The common source-adapter pipeline under `generated-go-integration` remains a
shared producer dependency; its eventual ownership migration is still open.
Producer validation runs against its exact committed inventory; no host-code
allowlist expansion permits reuse of changed guest/build inputs. The current
installer and host source identity are recorded separately. `public-source.json`
binds their installed source inventory to `installation-inputs.json`, the
registered binding and the immutable producer. All outputs remain UNQUALIFIED
and release-ineligible. The stable checkout and release ledgers are untouched.

The native core/owner interface lives in `internal/nativewire` and `internal/host`;
profile-specific runtime glue/factory templates live in `scripts/runtime_native`.
`generate_runtime.NATIVE_HANDWRITTEN_FILES` owns those runtime files separately
from the stable handwritten set. No old generated runtime is copied into
the selected product. The selected factory has no fallback, and acceptance adds
a legacy-Serve tripwire. Both Go and Python must fail when the native factory is
disabled. Ordinary checkout factory selection remains stable12.3.3.

`Selected public candidate` CI installs the same verified13.2 artifact on macOS
arm64/Linux x86_64. The initial gate runs existing TCP/Pipe, capacity, fatal cause,
isolation and default-timeout tests, host/owner units, Python transaction and
Snapshot/Fork smoke, exact runtime identity and factory-disable controls. Limits
are8GiB owned output/producer/handoff,8GiB free,40minutes per OS. This initial gate
is not the full #132 acceptance: precision settings, real completion/fault fixtures,
original22/88/38/G1/G2/P1 oracle rebinding and installed-wheel coverage remain.
Their completion and the #128 total upgrade-cost judgment retain the fixed exit.
