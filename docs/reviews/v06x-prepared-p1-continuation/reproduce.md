# P1 continuation reproduction (not P2–P6 or Qualification)

Use the exact source_commit in the CI run, confirmed with
`python3 scripts/git_identity.py inspect HEAD`. Keep the checkout committed and
clean. The source compilation, unit and development-runtime steps are defined in
[prepared-product.yml](../../../.github/workflows/prepared-product.yml).

## Native reference

The local control used the existing pinned arm64 image, not a rebuilt MariaDB:

```sh
docker run -d --rm --name mariamem-prepared-p1-native \
  -e MARIADB_ALLOW_EMPTY_ROOT_PASSWORD=1 -e MARIADB_ROOT_HOST=% \
  -e MARIADB_DATABASE=test -p 127.0.0.1:49469:3306 \
  mariadb@sha256:805c8e104bd563d5bfa24fadd3f31cd419ea859cb5277f32b5dbf2db714f9ed1
```

After the server's readiness log, use Python3.14 with PyMySQL1.2.3:

```sh
python tests/v06_prepared_p1_probe.py --native-port 49469 --output native-p1.json
docker stop mariamem-prepared-p1-native
```

The probe owns only its `test.prepared_p1_items` table and
`test.prepared_p1_proc` routine in this disposable DB. It drops/recreates those
objects for repeatability. Raw error packets must contain1064/42000 or1243/HY000
as appropriate; PyMySQL exception translation is not the error oracle. Compare
the complete descriptor packets to the committed native fixture; do not normalize
away flags, widths, charset or names to obtain a match. Native and guest errors
may have different contextual messages; errno and SQLSTATE are fixed here.

## Newly generated development host

On the fresh Linux arm64 builder, run the existing formal source command at the
same exact source_commit as the native stage:

```sh
python3 scripts/build_generated_guest.py --development-output "$P1_GUEST_OUT"
```

Transfer that complete checksum-bound directory to the native target, then use
Go1.26.8 and Python3.14 with pytest8.4.2/PyMySQL1.2.3:

```sh
python scripts/regenerate_release_guest.py --development \
  --guest-dir "$P1_GUEST_OUT" --output "$P1_DEV_OUT"
python tests/check_prepared_p1_binding.py \
  --runtime "$P1_DEV_OUT/product/internal/generatedgo"
python -m pytest -q "$P1_DEV_OUT/product/tests/test_thread_lifetime_binding.py"
PYTHONPATH="$P1_DEV_OUT/product/python" python tests/v06_prepared_p1_probe.py \
  --host "$P1_DEV_OUT/mariamem-dev-host" \
  --reference tests/fixtures/prepared-p1-native.json --output guest-p1.json
```

Outputs must be fresh absolute external directories satisfying the existing
development route's path/provenance rules. Follow the source-builder prerequisites
in [development](../../development.md#single-pass-unqualified-guest-development).
Do not reuse the earlier c63b563 guest receipt with changed host Go inputs: the
cross-commit source check must reject it. That earlier artifact was inspected and
translated for binding review only. The new CI recompiles at its own source SHA.

The development command already runs the bounded SQL/transaction/Snapshot/Fork/
Close smoke and returns UNQUALIFIED only on success. Source errors, any strict
binding mismatch or a native descriptor difference stop this P1 gate. Do not
update expected bytes or skip the failing case to turn a difference into PASS.
This does not run prepared EXECUTE, LONG_DATA, prepared CALL result consumption,
required Connector/Python consumers, independent canonical reproduction or the
full J1 forced-schedule failure oracle. Those remain P2–P6 work.
