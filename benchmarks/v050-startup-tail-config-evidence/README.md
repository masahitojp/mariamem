# InnoDB setting spike evidence

The [report](../v050-startup-tail-config-spike.md) owns interpretation.
`config-build.json` binds source and disposable prototype identities and records
the SQL probes of both settings. `config-comparison-unrestricted.jsonl` contains
30 complete alternating pairs; `config-summary.json` is produced by the
tracked `reduce_config.py` from those exact records. `config-unrestricted-console.log`
records successful completion. The initial sandbox attempt could not listen on
localhost and is retained in `config-failure-00-flush-sync-1.txt`; its empty
comparison output is excluded. `SHA256SUMS` checks the copied evidence.
