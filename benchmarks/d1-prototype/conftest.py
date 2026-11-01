import pytest
import entry

@pytest.fixture(scope='session')
def django_db_setup(django_db_setup):
    entry.manager = entry.Manager()
    try:
        yield
    finally:
        entry.manager.close()


def pytest_sessionfinish(session, exitstatus):
    if entry.manager and entry.manager.teardown:
        entry.manager.teardown.close()
