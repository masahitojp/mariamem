import pytest
import entry

@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        entry.manager = entry.Manager()
    try:
        yield
    finally:
        with django_db_blocker.unblock():
            entry.manager.close()


def pytest_sessionfinish(session, exitstatus):
    if entry.manager and entry.manager.teardown:
        entry.manager.teardown.close()
