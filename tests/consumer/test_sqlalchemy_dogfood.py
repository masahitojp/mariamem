"""User/Address ORM Quick Start adaptation; run with run_sqlalchemy.py.

Reference: https://docs.sqlalchemy.org/en/20/orm/quickstart.html
MySQL requires explicit VARCHAR lengths; add a unique name for constraint tests.
"""
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
import time

import mariamem
import pytest
import sqlalchemy
from sqlalchemy import (ForeignKey, String,
                        URL, create_engine, event, func, inspect, select, text)
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "user_account"
    __table_args__ = {"mysql_engine": "InnoDB"}
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(30), unique=True)
    fullname: Mapped[str | None] = mapped_column(String(120))
    addresses: Mapped[list["Address"]] = relationship(
        back_populates="user", cascade="all, delete-orphan")


class Address(Base):
    __tablename__ = "address"
    __table_args__ = {"mysql_engine": "InnoDB"}
    id: Mapped[int] = mapped_column(primary_key=True)
    email_address: Mapped[str] = mapped_column(String(120))
    user_id: Mapped[int] = mapped_column(ForeignKey("user_account.id"))
    user: Mapped["User"] = relationship(back_populates="addresses")


def engine_for(db, record):
    info = db.connection_info()
    # Ordinary URL adaptation, not a mariamem-specific dialect or pool setting.
    engine = create_engine(URL.create(
        "mysql+pymysql", username=info["user"], password=info["password"],
        host=info["host"], port=info["port"], database=info["database"]))
    record.update(connects=0, checkouts=0, checkins=0, resets=0, closes=0,
                  peak_checked_out=0, sql=[])
    active = set()

    @event.listens_for(engine, "connect")
    def connected(connection, connection_record):
        record["connects"] += 1

    @event.listens_for(engine, "checkout")
    def checked_out(connection, connection_record, proxy):
        record["checkouts"] += 1
        active.add(id(connection))
        record["peak_checked_out"] = max(record["peak_checked_out"], len(active))

    @event.listens_for(engine, "checkin")
    def checked_in(connection, connection_record):
        record["checkins"] += 1
        active.discard(id(connection))

    @event.listens_for(engine, "reset")
    def reset(connection, connection_record, state):
        record["resets"] += 1

    @event.listens_for(engine, "close")
    def closed(connection, connection_record):
        record["closes"] += 1

    @event.listens_for(engine, "before_cursor_execute")
    def statement(connection, cursor, sql, parameters, context, executemany):
        record["sql"].append(sql)

    return engine


def prepare(engine):
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(name="seed@example.test", fullname=None)
        user.addresses.append(Address(email_address="seed@example.test"))
        session.add(user)
        session.commit()


def reaped(db, pids, directory):
    assert db.closed and not directory.exists()
    for pid in pids.values():
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)


@pytest.fixture(scope="session", autouse=True)
def audit():
    assert mariamem.__version__ == "0.3.0"
    assert Path(mariamem.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    native_override = os.environ.get("MARIAMEM_NATIVE_DIR")
    result = {"mode": os.environ["DOGFOOD_MODE"], "python": platform.python_version(),
              "native_dir_override": native_override,
              "platform": platform.platform(), "architecture": platform.machine(),
              "packages": {name: importlib.metadata.version(name)
                           for name in ("mariamem", "SQLAlchemy", "PyMySQL", "pytest")},
              "cases": [], "templates": []}
    result["wheel_origin"] = json.loads(importlib.metadata.distribution("mariamem").read_text("direct_url.json"))
    manifest_path = (Path(native_override) / "manifest.json" if native_override
                     else Path(mariamem.__file__).parent / "_native/manifest.json")
    result["native_manifest"] = json.loads(manifest_path.read_text())
    try:
        yield result
    finally:
        Path(os.environ["DOGFOOD_EVIDENCE"]).write_text(json.dumps(result, indent=2) + "\n")


@pytest.fixture(scope="session")
def prepared(audit):
    if audit["mode"] == "start":
        yield None
        return
    record = {}
    started = time.monotonic()
    with mariamem.start() as template:
        pids, directory = template.diagnostics, template.log_path.parent
        engine = engine_for(template, record)
        try:
            prepare(engine)
        finally:
            engine.dispose()
        template.wait_disconnected()
        with template.snapshot() as snapshot:
            reaped(template, pids, directory)
            record["setup_snapshot_ms"] = (time.monotonic() - started) * 1000
            audit["templates"].append(record)
            saved = snapshot.path
            yield snapshot
        assert not saved.exists()


@pytest.fixture
def app(request, prepared, audit):
    record = {"test": request.node.name}
    audit["cases"].append(record)
    started = time.monotonic()
    db = prepared.fork() if prepared is not None else mariamem.start()
    record["database_id"] = db.id
    pids, directory = db.diagnostics, db.log_path.parent
    engine = None
    try:
        engine = engine_for(db, record)
        if prepared is None:
            prepare(engine)
        with engine.connect() as connection:
            assert connection.scalar(select(func.count()).select_from(User)) == 1
            assert connection.scalar(select(func.count()).select_from(Address)) == 1
            assert connection.scalar(select(User.name)) == "seed@example.test"
            record["server_version"] = connection.scalar(text("SELECT VERSION()"))
        record["ready_ms"] = (time.monotonic() - started) * 1000
        record["dialect"] = {"name": engine.dialect.name,
                             "is_mariadb": engine.dialect.is_mariadb,
                             "version": engine.dialect.server_version_info}
        record["pool"] = {"class": type(engine.pool).__name__,
                          "size": engine.pool.size(),
                          "max_overflow": engine.pool._max_overflow}
        yield engine, db, record
        if not db.closed:
            with engine.connect() as connection:
                record["final_users"] = connection.scalar(select(func.count()).select_from(User))
        assert engine.pool.checkedout() == 0
    finally:
        if engine is not None:
            engine.dispose()
        try:
            if not db.closed:
                db.wait_disconnected()
                record["after_dispose_sessions"] = db.status()["active_connections"]
        finally:
            db.close()
        reaped(db, pids, directory)
        record["cleanup"] = "PASS"


def test_01_committed_data_without_cleanup(app):
    engine, db, record = app
    with Session(engine) as session, session.begin():
        session.add(User(name="committed_by_test_a"))
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(User)) == 2
    # Intentionally no cleanup SQL: fixture destroys the whole database.


def test_02_next_database_cannot_see_committed_data(app, audit):
    engine, db, record = app
    previous = audit["cases"][-2]
    assert previous["test"] == "test_01_committed_data_without_cleanup"
    assert previous["final_users"] == 2 and previous["cleanup"] == "PASS"
    assert previous["database_id"] != db.id
    with Session(engine) as session:
        assert session.scalar(select(User).where(User.name == "committed_by_test_a")) is None


def test_03_update_commit_and_delete(app):
    engine, _, _ = app
    with Session(engine) as session, session.begin():
        user = session.scalar(select(User))
        user.fullname = "Updated"
        assert user.addresses[0].email_address == "seed@example.test"
        assert session.scalar(select(User).join(User.addresses).where(
            Address.email_address == "seed@example.test")) is user
    with Session(engine) as session, session.begin():
        assert session.scalar(select(User.fullname)) == "Updated"
        session.delete(session.scalar(select(Address)))
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Address)) == 0


def test_04_explicit_business_rollback(app):
    engine, _, _ = app
    with Session(engine) as session:
        session.add(User(name="rolled-back@example.test"))
        session.flush()
        session.rollback()
        assert session.scalar(select(User).where(User.name == "rolled-back@example.test")) is None


@pytest.mark.parametrize("violation,code", [("unique", 1062), ("not_null", 1048), ("foreign_key", 1452)])
def test_05_constraint_error_is_recoverable(app, violation, code):
    engine, db, _ = app
    invalid = {"unique": User(name="seed@example.test"), "not_null": User(name=None),
               "foreign_key": Address(user_id=9999, email_address="missing@example.test")}[violation]
    with Session(engine) as session:
        session.add(invalid)
        with pytest.raises(IntegrityError) as error:
            session.commit()
        assert error.value.orig.args[0] == code
        session.rollback()  # Required SQLAlchemy failed-transaction recovery, not test cleanup.
        assert session.scalar(select(func.count()).select_from(User)) == 1
    assert not db.closed


def test_06_metadata_and_autocommit(app):
    engine, _, _ = app
    metadata = inspect(engine)
    assert set(metadata.get_table_names()) == {"user_account", "address"}
    assert metadata.get_pk_constraint("user_account")["constrained_columns"] == ["id"]
    assert metadata.get_foreign_keys("address")[0]["referred_table"] == "user_account"
    assert metadata.get_unique_constraints("user_account")[0]["column_names"] == ["name"]
    reflected = sqlalchemy.MetaData()
    reflected.reflect(bind=engine)
    assert set(reflected.tables) == {"user_account", "address"}
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(text("INSERT INTO user_account(name) VALUES ('autocommit@example.test')"))
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM user_account")) == 2


def test_07_normal_pool_and_session_state(app):
    engine, _, record = app
    with engine.connect() as first, engine.connect() as second:
        a = first.scalar(text("SELECT CONNECTION_ID()"))
        b = second.scalar(text("SELECT CONNECTION_ID()"))
        assert a != b
        first.execute(text("SET @dogfood_state = 42"))
        first.execute(text("CREATE TEMPORARY TABLE dogfood_temp(id INT)"))
        assert second.scalar(text("SELECT @dogfood_state")) is None
        with pytest.raises(ProgrammingError) as error:
            second.scalar(text("SELECT COUNT(*) FROM dogfood_temp"))
        assert error.value.orig.args[0] == 1146
        first.execute(text("INSERT INTO user_account(name) VALUES ('uncommitted@example.test')"))
    with engine.connect() as reused, engine.connect() as another:
        states = []
        for connection in (reused, another):
            connection_id = connection.scalar(text("SELECT CONNECTION_ID()"))
            assert connection_id in {a, b}
            assert connection.scalar(text("SELECT COUNT(*) FROM user_account WHERE name='uncommitted@example.test'")) == 0
            # Observe ordinary pool reset semantics; don't silently clear session state.
            states.append(connection.scalar(text("SELECT @dogfood_state")))
            if connection_id == a:
                assert connection.scalar(text("SELECT COUNT(*) FROM dogfood_temp")) == 0
                record["temporary_table_survived_checkin"] = True
        record["reused_session_variables"] = states
        assert sorted(value for value in states if value is not None) == [42]
    assert record["connects"] == 2


def test_08_shutdown_with_idle_pool_connections(app):
    engine, db, record = app
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT 1")) == 1
    # Application closes its DB while the pool still owns an idle socket.
    pids, directory = db.diagnostics, db.log_path.parent
    db.close()
    engine.dispose()
    reaped(db, pids, directory)
    record["database_first_shutdown"] = "PASS"


def test_09_matched_rowcount_observation(app):
    engine, _, record = app
    with engine.begin() as connection:
        record["noop_update_rowcount"] = connection.execute(text(
            "UPDATE user_account SET name=name WHERE id=1")).rowcount
    assert record["noop_update_rowcount"] == 1
