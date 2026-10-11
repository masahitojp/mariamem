#!/bin/bash
set -eu
WORK=/workspace/mariamem/build/experiment-work/v05-mariadb-132-feasibility
export PYTHONPATH="$WORK/temp/dev-native/product/python"
export MARIAMEM_TEST_HOST="$WORK/temp/dev-native/mariamem-dev-host"
export MARIAMEM_TEST_DEFAULT=1 MARIAMEM_DEV_EXPECTED_VERSION=13.2.0
export TMPDIR="$WORK/temp/tmp"
cd "$WORK/worktree"
exec "$WORK/temp/venv/bin/python" -m pytest tests/test_owned_snapshot.py tests/test_python_wire.py tests/test_python_multiclient.py tests/test_python_timeout.py::test_normal_close_is_idempotent -q --junitxml="$WORK/evidence/acceptance.xml"
