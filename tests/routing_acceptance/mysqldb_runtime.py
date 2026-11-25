"""Real-guest MySQLdb and SQLAlchemy mysql+mysqldb routing verification.

Run on environments with native mysqlclient (libmysqlclient / mariadb-connector-c).
Keeps the existing tests/routing_acceptance/run.py 17-case receipt contract separate.
"""
import argparse
import importlib.metadata
import socket
import sys
import threading

import mariamem
import MySQLdb
from MySQLdb import connect as saved_mysqldb_connect
from sqlalchemy import URL, create_engine, text

from mariamem import routing


class Sentinel:
    def __init__(self):
        self.socket = socket.socket()
        self.socket.bind(("127.0.0.1", 0))
        self.socket.listen()
        self.socket.settimeout(0.1)
        self.port = self.socket.getsockname()[1]
        self.attempts = 0
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.loop)
        self.thread.start()

    def loop(self):
        while not self.stop.is_set():
            try:
                conn, _ = self.socket.accept()
            except socket.timeout:
                continue
            self.attempts += 1
            conn.close()

    def close(self):
        self.stop.set()
        self.thread.join()
        self.socket.close()


def query(conn, sql, args=None):
    cur = conn.cursor()
    try:
        cur.execute(sql, args)
        return cur.fetchall() if cur.description else ()
    finally:
        cur.close()


def expect_routing_error(code, fn):
    try:
        fn()
    except routing.RoutingError as error:
        assert error.code == code, (error.code, code)
        assert "mysqldb-private-secret" not in str(error)
        assert "mysqldb-private-secret" not in repr(error.diagnostics)
        return
    raise AssertionError(f"Expected RoutingError({code})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    args = parser.parse_args()

    print(
        "mysqldb_runtime:",
        "mysqlclient=" + importlib.metadata.version("mysqlclient"),
        "SQLAlchemy=" + importlib.metadata.version("SQLAlchemy"),
        "client=" + MySQLdb.get_client_info(),
        flush=True,
    )

    sentinel = Sentinel()
    original = dict(
        host="127.0.0.1",
        port=sentinel.port,
        user="application",
        password="mysqldb-private-secret",
        database="app",
        autocommit=True,
        connect_timeout=2,
    )
    try:
        with mariamem.start(host_binary=args.host) as setup:
            with MySQLdb.connect(**dict(setup.connection_info(), autocommit=True)) as conn:
                query(conn, "CREATE DATABASE app")
                query(conn, "CREATE TABLE app.marker(id INT PRIMARY KEY, value VARCHAR(64))")
                query(conn, "INSERT INTO app.marker VALUES(1, 'seed')")
            setup.wait_disconnected()
            with setup.snapshot() as baseline:
                with baseline.fork() as a, baseline.fork() as b:
                    for db, value in ((a, "A"), (b, "B")):
                        info = dict(db.connection_info(), database="app", autocommit=True)
                        with MySQLdb.connect(**info) as conn:
                            query(conn, "UPDATE marker SET value=%s WHERE id=1", (value,))

                    url = URL.create(
                        "mysql+mysqldb",
                        username=original["user"],
                        password=original["password"],
                        host=original["host"],
                        port=original["port"],
                        database="app",
                    )
                    engine = create_engine(url, pool_size=2, max_overflow=0, pool_timeout=2)
                    try:
                        with routing.install(
                            profiles={"app": routing.Profile("127.0.0.1", sentinel.port, "app")},
                            drivers=("MySQLdb",),
                        ) as routes:
                            routes.register_engine(engine, profile="app", ownership="test")

                            # Missing target before bind
                            expect_routing_error("missing_target", lambda: MySQLdb.connect(**original))

                            with routes.bind("app", a):
                                observed = []
                                for factory in (
                                    lambda: MySQLdb.connect(**original),
                                    lambda: MySQLdb.Connect(**original),
                                    lambda: saved_mysqldb_connect(**original),
                                    lambda: MySQLdb.connect(
                                        original["host"],
                                        original["user"],
                                        original["password"],
                                        original["database"],
                                        original["port"],
                                    ),
                                    lambda: MySQLdb.connect(
                                        host=original["host"],
                                        port=original["port"],
                                        user=original["user"],
                                        passwd=original["password"],
                                        db=original["database"],
                                    ),
                                    lambda: MySQLdb.connect(**dict(original, ssl_mode="PREFERRED")),
                                    lambda: MySQLdb.connect(**dict(original, ssl=False)),
                                ):
                                    with factory() as conn:
                                        observed.append(query(conn, "SELECT value FROM marker WHERE id=1")[0][0])
                                assert observed == ["A"] * 7, observed

                                # Refused options and schema mismatch before dial
                                expect_routing_error(
                                    "schema_mismatch",
                                    lambda: MySQLdb.connect(**dict(original, database="other_app")),
                                )
                                expect_routing_error(
                                    "option_file",
                                    lambda: MySQLdb.connect(**dict(original, read_default_file="/tmp/my.cnf")),
                                )
                                expect_routing_error(
                                    "transport_conflict",
                                    lambda: MySQLdb.connect(**dict(original, unix_socket="/tmp/mysql.sock")),
                                )
                                expect_routing_error(
                                    "tls_unavailable",
                                    lambda: MySQLdb.connect(**dict(original, ssl=True)),
                                )
                                expect_routing_error(
                                    "tls_unavailable",
                                    lambda: MySQLdb.connect(**dict(original, ssl={"ca": "/nonexistent.pem"})),
                                )
                                expect_routing_error(
                                    "tls_unavailable",
                                    lambda: MySQLdb.connect(**dict(original, ssl_mode="REQUIRED")),
                                )
                                expect_routing_error(
                                    "unsupported_options",
                                    lambda: MySQLdb.connect(**dict(original, compress=True)),
                                )

                            # SQLAlchemy mysql+mysqldb QueuePool generation switching and session isolation
                            seen = []
                            for idx, db in enumerate((a, a, b, a)):
                                with routes.bind("app", db):
                                    with engine.connect() as conn:
                                        assert conn.scalar(text("SELECT @mysqldb_route_scope")) is None
                                        conn.execute(text("SET @mysqldb_route_scope = :v"), {"v": f"s{idx}"})
                                        seen.append(conn.scalar(text("SELECT value FROM marker WHERE id=1")))
                            assert seen == ["A", "A", "B", "A"], seen

                            # Custom creator rejection
                            custom = create_engine(url, creator=lambda: None)
                            try:
                                expect_routing_error(
                                    "custom_creator",
                                    lambda: routes.register_engine(custom, profile="app", ownership="test"),
                                )
                            finally:
                                custom.dispose()
                    finally:
                        engine.dispose()
        assert sentinel.attempts == 0, f"Original sentinel contacted {sentinel.attempts} times"
        print("mysqldb_runtime: PASS", flush=True)
        return 0
    finally:
        sentinel.close()


if __name__ == "__main__":
    sys.exit(main())
