# Contributing

See [development](docs/development.md) for pinned builds and acceptance tests.
Changes to SQL behavior should include a regression exercised through a real
MySQL driver. Lifecycle changes should check process and temporary-file cleanup.

Preserve upstream copyright and license notices. Record guest changes as source
patches or overlays and update release input/provenance records when dependencies
change. Do not commit generated DB data, local runtime caches, or native binaries.
