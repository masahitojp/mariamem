# Bounded v0.5 correctness probes

These diagnostic templates run unmodified canonical helpers in a small owned
module. They do not modify the product, regenerate the guest or certify release
readiness. See [judgment and evidence](../../../docs/reviews/v050-correctness-judgment.md).

Use task-owned Go1.26.8 GOCACHE/GOPATH/GOMODCACHE and a new output directory:

```sh
python3 benchmarks/spikes/v050-correctness/probe.py --output ../temp/probes
```

An ordinary command FAIL means its contract oracle failed. A `-race` FAIL with
`WARNING: DATA RACE` is a detected reduced conflict. A mmap diagnostic PASS does
not prove race freedom. Setup/build errors are labeled ERROR and stop collection.
Current known failures remain outside product package discovery; no product
check is weakened. The report retains byte inventories and all command outcomes.

The read-only 32-bit extraction is a diagnostic alternative only, never an
adopted load implementation. The plain conflicting counters have no final-value
correctness assertion; they compare detector visibility on heap/mmap backing.
Native Ubuntu x86_64 remains unexecuted in the recorded local campaign.
