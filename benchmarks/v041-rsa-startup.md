# v0.4.1 RSA startup audit

Source: released `v0.4.0`, **39537e9bb2fbbc28315e1ff672960ad734a9e399**.
Runtime: normal public `Options{}` direct-linked generated-Go. macOS27.0.1
arm64 / Apple M1 reference, Go1.26.8. No production/guest source was changed.
Results: [v041-rsa-results.json](v041-rsa-results.json); reproducible probe:
[v041_rsa.py](v041_rsa.py) and [v041rsa/main.go](v041rsa/main.go).

## The proposed OFF setting is already released

`guest/source.patch` supplies all three arguments under `L4M_RESIDENT`:

```text
--caching-sha2-password-private-key-path=/mariamem-auth/private.pem
--caching-sha2-password-public-key-path=/mariamem-auth/public.pem
--caching-sha2-password-auto-generate-rsa-keys=OFF
```

This dates to **b77f64194e0de19b56ff29cb8b8dde569db20b59** (prepared public test
RSA keys), and was preserved through canonical legacy-EH regeneration.
The probe decodes the generated initial-data declaration and confirms exactly
one occurrence of the OFF option. Decoded data SHA256 is
`22b9b269097cfda323244d3d51cdab118eb65cde043409fa59865130e502c5a0`;
compiled guest identity is
`33d351b4edaddce9dd52db375c6c3f2a5ff13c259bc6788794daf5bf8bf3e008`.
This establishes actual generated artifact evidence, rather than relying only
on an old source patch or dependency list.

Each fresh guest provisions the fixed PUBLIC, NON-SECRET, TEST-ONLY keypair into
its private MemFS. These are not production credentials. The plugin remains
enabled. `resident.inc` requires loaded keys before readiness and the explicit
auth diagnostic invokes the real pinned plugin callback; missing/corrupt keys
fail rather than generate replacements. Normal wire credentials and the embedded
plugin callback are different acceptance boundaries.

## Acceptance and exploratory released-OFF measurements

The generated `auth-check` returned **PASS, generated=false,
actual_callback=true**. That bounded mock non-TLS callback covers public-key
request/RSA OAEP password, successful password, wrong-password and malformed
ciphertext paths; it does not prove full network account/grant authentication.
Every public Start trial verified SELECT1, a second session, invalid credentials,
all sessions disconnected, reconnect, successful query and repeated clean Close.
Focused fixture/provisioning/plugin-hook Python checks: **5 passed, 3 skipped**
(the opt-in external-source cases were unavailable). The actual generated plugin
callback above executed and passed; skipped cases are not claimed as passing.

Thirty **independent processes**, serialized under the same host measurement
lock as the other lanes, used no native override and no executable provisioning.
No slow runs were removed. CPU uses current-process user+system Getrusage from
immediately before public Start to the indicated boundary. Build/process launch
and later auth smoke/Close are outside these latency/CPU boundaries.

| Boundary | min | p50 | p95 | max |
| --- | ---: | ---: | ---: | ---: |
| public Start return | 38.45 ms | 45.42 ms | 1055.45 ms | 1056.12 ms |
| public Start → SELECT1 | 40.14 ms | 47.47 ms | 1058.40 ms | 1058.80 ms |
| CPU to Start return | 0.02628 s | 0.03008 s | 0.04780 s | 0.04898 s |
| CPU to first SQL | 0.03042 s | 0.03435 s | 0.05512 s | 0.05610 s |

8/30 first-SQL trials were ≥900ms (26.7%). This retains the known guest-side
startup tail; no claim is made that all sampled tails were individually traced.
This is a diagnostic sample, not a rerun of the canonical performance campaign.

## Decision

There is **no new ON→OFF experiment to integrate**: released v0.4.0 is already
OFF. Building an artificial ON guest solely to rediscover the historical RSA
cost would require a new source/guest/generated artifact and is unnecessary to
answer whether shipping OFF is a new v0.4.1 opportunity. No counterfactual CPU
saving is inferred from these released-OFF numbers.

Adding the same option again would have zero incremental configuration effect.
Keep the existing key/plugin semantics and focused tests; correct stale roadmap
wording after the human fan-in decision. No source, runtime flags, synchronization,
MariaDB semantics or auth behavior changed on this experiment branch.

**SAFE BUT BENEFIT IS NEGLIGIBLE** — specifically, the proposed extra disabling
is redundant with the released artifact, not evidence that the original RSA
optimization was negligible.
