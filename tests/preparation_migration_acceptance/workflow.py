"""Native preparation acceptance, selected explicitly by its source-bound runner."""
import pytest
from sqlalchemy.exc import IntegrityError
import application
from observe import record

pytestmark = [pytest.mark.shadow_maria, pytest.mark.parametrize(
    'cycle', [pytest.param('first', marks=pytest.mark.xdist_group('first')),
              pytest.param('second', marks=pytest.mark.xdist_group('second'))])]


def test_01_application_commit(mariamem_app_db, mariamem_router, cycle):
    assert mariamem_router._target().database is mariamem_app_db
    assert application.users() == [(1,'legacy',0),(2,'seed',5)]
    application.create_user()
    assert application.users() == [(1,'legacy',0),(2,'seed',5),(3,'created',7)]
    record('test_pass', name='commit', child=mariamem_app_db.id, cycle=cycle)


def test_02_next_test_has_prepared_state(mariamem_app_db, mariamem_router, cycle):
    assert mariamem_router._target().database is mariamem_app_db
    assert application.users() == [(1,'legacy',0),(2,'seed',5)]
    with pytest.raises(IntegrityError) as failure:
        application.invalid_address()
    assert failure.value.orig.args[0] == 1452
    assert application.users() == [(1,'legacy',0),(2,'seed',5)]
    record('test_pass', name='independent_initial_state', child=mariamem_app_db.id, cycle=cycle)
