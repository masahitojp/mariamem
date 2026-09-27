# Prepared RSA keys: causal experiment

Branch: `experiment/prepared-auth-keys`. This is disposable experimental code,
not a production key-provisioning proposal. Measurement results are pending CI;
no RSA-generation hypothesis has been confirmed yet.

## Source facts and setup

The pinned `plugin/auth_mysql_sha2/mysql_sha2.c::init_keys()` generates keys only
when both paths retain their default values, both files are absent, and
`auto_generate_rsa_keys` is enabled. It then calls `ssl_loadkeys()` regardless
of generation. `ssl_stuff.c::ssl_genkeys()` calls `EVP_RSA_gen(2048)` and writes
private and public PEM files. `ssl_loadkeys()` parses the private PEM, reads the
public PEM and installs the plugin's private/public key state. Upstream returns
success from `init_keys()` even when those helpers fail; ACTIVE alone is therefore
insufficient evidence of working RSA state.

The default relative files are `private_key.pem` and `public_key.pem`, resolved
from the guest working directory (not explicitly from `--datadir`). The explicit
experimental options remove that ambiguity:

```
--caching-sha2-password-private-key-path=/auth-keys/private.pem
--caching-sha2-password-public-key-path=/auth-keys/public.pem
```

`benchmarks/prepared_auth_keys.py` generates one disposable 2048-bit RSA pair
with OpenSSL, checks the private key and derives its public PEM before timing.
The host maps that temporary directory at `/auth-keys` only for existing-key runs.
No private key is committed or uploaded; only its hash is recorded, and setup
deletes the pair afterward. Input files must remain byte-identical across runs.

Both conditions use the same experimentally instrumented WASM/AOT. The separate
`guest/experimental.patch` adds success/failure events around the *unchanged*
generation predicate and both helper calls, plus the explicit startup options.
It does not disable the plugin or change cache defaults. Generation/load failure,
the wrong branch, absent diagnostics or collector overflow fails the experiment.
After first SQL (outside its latency interval), each startup also verifies the
plugin is ACTIVE and exposes a public key; existing-key runs require that key to
match the prepared PEM. This probe contributes to lifecycle CPU/RSS observations,
but not the measured first-SQL latency.

## Measurement protocol

Dispatch `guest-build-boundary.yml` on this branch with `auth_key_experiment=true`.
Linux builds the changed guest once. Both platform jobs use the existing immutable
WASM/AOT identity, hash and provenance verification, and never rebuild between
conditions. The workflow does not publish anything.

Each platform runs two warmup pairs, then 20 measured pairs, alternating A/B and
B/A order. Each condition invokes the canonical Go runner with one measurement,
the same 1,000-row/32-character fixture and first-SQL definitions, ×1/4/8, CPU/RSS
sampling and initialization diagnostics. This pairs complete runner invocations,
not simultaneous opposing conditions; each invocation prepares its own equivalent
fixture. Its canonical worker order remains 1/4/8. Per-DB observations within a
parallel batch are correlated; their quantiles are not independent trial counts.

Raw files and `summary.json` / `summary.md` are retained in the workflow's
`initialization-<platform>-<source-sha>` artifacts under
`benchmarks/results/init-auth-keys/`. The JSON contains commit, Go environment,
AOT provenance, test-key hashes, raw-file identities, branch-verification counts,
latency p50/p95 and callback/process/thread CPU/allocation/mapping summaries.
Compare each platform's paired conditions, not cross-platform absolute hardware
performance. Sampled CPU misses startup/exit edges; RSS double-counts shared pages.

## Authentication and semantic scope

Source fact: the existing embedded guest uses `--skip-grant-tables`; its public
SQL endpoint does not exercise a full caching_sha2_password authentication
exchange. This experiment preserves that behavior. Successful PEM parsing,
ACTIVE plugin and exact exposed public-key equality prove the load branch and
installed key identity, **not** end-to-end password/RSA challenge authentication.
There is no authentication bypass introduced by the experimental condition.
Production provisioning/security and a dedicated authentication exchange test
remain outside this causal measurement.

## Results to complete after CI

Record control generation versus existing-key load proof on both platforms;
callback wall/process/thread CPU p50/p95; post-srv plugins and complete embedded
init; Fork→SQL ×1/4/8 and paired differences; Aria mapping growth and ready RSS.
Distinguish measured differences from inferred causal attribution and remaining
unknowns. Keep raw results ignored. Do not productionize this branch.

## Implication for 0.2 architecture

Unknown until the paired measurements complete. A large callback and end-to-end
reduction with unchanged Aria mappings would support a small cold-start/prepared
state probe before continuation. A small reduction would require further plugin
attribution; substantial remaining init/restore/memory cost may still justify
continuation or storage probes. No architecture is selected here.
