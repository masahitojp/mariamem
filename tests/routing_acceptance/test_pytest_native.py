"""Real session baseline/function child lifecycle through the early pytest API."""
import os
import pytest
import pymysql

pytestmark = [pytest.mark.skipif(not os.environ.get("MARIAMEM_ROUTING_HOST"), reason="explicit routing native host required"),
              pytest.mark.usefixtures("mariamem_routed")]


@pytest.fixture(scope="session")
def mariamem_options():
    return {"host_binary": os.environ["MARIAMEM_ROUTING_HOST"]}


@pytest.fixture(scope="session")
def mariamem_snapshot(mariamem_server):
    with pymysql.connect(**mariamem_server.connection_info(), autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("CREATE DATABASE app")
            cursor.execute("CREATE TABLE app.users(id INT PRIMARY KEY) ENGINE=InnoDB")
            cursor.execute("INSERT INTO app.users VALUES(1)")
    mariamem_server.wait_disconnected()
    with mariamem_server.snapshot() as baseline:
        yield baseline


@pytest.mark.parametrize("test_number", range(4))
def test_application_queries_use_independent_children(test_number):
    # Application connection settings stay fixed, including the original
    # endpoint. The fixture supplies the worker's current child instead.
    with pymysql.connect(host="127.0.0.1", port=3307, user="application",
                         password="not-a-real-secret", database="app") as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM users ORDER BY id")
            assert cursor.fetchall() == ((1,),)
            cursor.execute("INSERT INTO users VALUES(2)")
        connection.commit()
