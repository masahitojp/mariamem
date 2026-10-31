# Parallel application model-case comparison

Experimental measurement harness for released mariamem0.6.0 and native-arm64
MariaDB12.3.3 through Testcontainers Go0.40.0. This is inspired by pgmem
modelcase, not a port of its SQL or a reproduction of its published numbers.
It has no triggers/views and makes no claim about that input support.

The same50 read cases and20 committed write cases use five InnoDB tables,
20categories/500products/1000users and40 sample orders. Every test verifies the
pristine state before running identical application SQL/assertions.

- mariamem: public mariamemtest fixture, one prepared Snapshot, independent
  Fork for every test including readers; MaxForks equals test parallelism.
- shared Testcontainers: one server/schema, read-only group in parallel, then
  serialized writing cases, reset after a previous writer.
- worker-schema Testcontainers: one server, one independently seeded schema
  per concurrent worker; reset only after a previous writer used that schema.

These isolation boundaries differ: Fork gives a separate embedded server,
schema reset leaves native global/server state shared. SQL/settings/durability
are not tuned to force a result. Native macOS versus Linux Docker VM and
skip-grants versus normal authentication remain real product differences.

The external driver times boot→test-process exit including all explicit
DB/pool/container cleanup; download/compile are outside. Ryuk starts inside
each fresh native test process. Timelines use one monotonic origin per suite;
span sums overlap and are never substituted for wall time.

First run the three-model parallelism1 pilot and a corrupted-seed negative
control. Only after they succeed, run parallelism1/2/4/8 with one labelled
warmup and five measured repetitions per cell, rotating model order.
The plan records bounds. The completed [comparison report](../parallel-modelcase.md)
contains medians/ranges, actual median-run timelines, raw results and limitations.
This measurement creates no new product or release acceptance gate.
