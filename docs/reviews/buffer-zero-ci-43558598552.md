# Buffer-zero candidate CI checkout correction

[Run43558598552](https://github.com/masahitojp/mariamem/actions/runs/43558598552)
failed on source_commit `003111b91c2140133d40c9af0db356b6e29fe8f9`.
The guest job completed two matching independent builds of guest
`77b2ab49a9927f15c899ad34f9f40e5f06ac42589b1d4f926fd0c5b0f1f19450`.
Both native jobs passed regeneration and its canonical build guard, then failed
standard check in the same two fixture contract tests (1913 Python tests passed).
Integration and the following buffer-control step did not execute in this run.

The default shallow native checkout omitted ancestor
`d8f66d9a5605b3b738b2175268a3734ee1c89a4a`, required by the fixture source-identity
lint. This is not a buffer-pool runtime or Connector/Python failure. The ancestor
is reachable from the candidate. The existing Development workflow already uses
`filter: blob:none` and `fetch-depth: 0` for this dependency; native candidate CI
now uses the same checkout settings. Guest/runtime inputs and test assertions
are unchanged. Related-issue lookup found no dedicated shallow-checkout issue;
no duplicate issue or external-Connector investigation was started.

Validation: existing `tests/test_fixture_design_contract.py`:24 PASS;
workflow YAML/native history configuration, public-source and diff checks.
Only CI configuration and this failure record change. No guest rebuild or
performance remeasurement is run locally. The existing canonical workflow binds
producer receipts to its exact candidate SHA, so retry is submitted through that
workflow rather than relabeling the prior successful build as a new-source run.
The [compact receipt](buffer-zero-ci-43558598552.json) keeps original source,
artifact ZIP hashes and failure identities. Retry results remain pending CI.
