"""Fixture API inspired by shibukawa/pgmem (MIT); see bundled notices."""
import pytest

from . import start


@pytest.fixture(scope="session")
def mariamem_options():
    return {}


@pytest.fixture(scope="session")
def mariamem_server(mariamem_options):
    with start(**mariamem_options) as server:
        yield server


@pytest.fixture(scope="session")
def mariamem_snapshot(mariamem_server):
    mariamem_server.wait_disconnected()
    with mariamem_server.snapshot() as saved:
        yield saved


@pytest.fixture
def mariamem_fork(mariamem_snapshot):
    with mariamem_snapshot.fork() as fork:
        yield fork


@pytest.fixture
def mariamem_connection_info(mariamem_fork):
    return mariamem_fork.connection_info()
