"""Two ordinary app tests, each bound to an independent imported child."""
import json
import os
from pathlib import Path

import application
from observe import record
from oracles import connect, differences, enforce_constraints, observe
import pytest

pytestmark = pytest.mark.shadow_maria


def original_baseline(db):
    with connect(db.connection_info()) as connection:
        actual = observe(connection)
    expected = json.loads(Path(os.environ['DUMP_REFERENCE']).read_text())['observation']
    assert not differences(expected, actual)
    return expected


def test_01_application_commit(mariamem_app_db, mariamem_router):
    assert mariamem_router._target().database is mariamem_app_db
    expected = original_baseline(mariamem_app_db)
    assert application.users() == [(1, 'legacy', 0), (2, 'seed', 5)]
    application.create_user()
    assert application.users() == [(1, 'legacy', 0), (2, 'seed', 5), (3, 'created', 7)]
    with connect(mariamem_app_db.connection_info()) as connection:
        actual = observe(connection)
        for key in ['values', 'procedure_results', 'function_results', 'revision']:
            assert actual[key] == expected[key]
    record('test_pass', name='commit', child=mariamem_app_db.id)


def test_02_next_test_has_imported_baseline(mariamem_app_db, mariamem_router):
    assert mariamem_router._target().database is mariamem_app_db
    original_baseline(mariamem_app_db)
    assert application.users() == [(1, 'legacy', 0), (2, 'seed', 5)]
    with connect(mariamem_app_db.connection_info()) as connection:
        assert enforce_constraints(connection) == [1452, 1062]
    assert application.users() == [(1, 'legacy', 0), (2, 'seed', 5)]
    record('test_pass', name='independent_initial_state', child=mariamem_app_db.id)
