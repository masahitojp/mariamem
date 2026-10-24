# Reproduce the bounded migration spike

This is a repository-authored example, not an imported existing application or
universal migration adapter. It uses Alembic1.18.4, SQLAlchemy2.0.54 and
PyMySQL1.2.3. All development dependency versions are fixed in `requirements.txt`;
pip's installation report records platform-specific archive identities.
No product dependency, driver route, guest patch or generated source is changed.

1. Check out the exact `source_commit` in the saved result. Verify it with
   `python scripts/git_identity.py inspect HEAD`; the checkout must be clean.
2. Prepare an owned experiment workspace with4GiB budget and8GiB free reserve.
   Create a Python3.14 venv inside its `temp/` directory. Install
   `tests/preparation_migration_spike/requirements.txt` with
   `pip --no-cache-dir --report <workspace>/evidence/dependencies.json`.
3. Run the receipt classifier tests:
   `python -m pytest tests/test_preparation_migration_spike.py -q`.
4. Use the workspace/disk guard to run:
   `python tests/preparation_migration_spike/run.py --runtime-root <repo> --source-commit <full-commit-SHA> --output <workspace>`.
   The runner builds and verifies the stamped Go1.26.10 host once, then executes
   the success, later-revision failure and seed failure scenarios. The negative
   pytest processes deliberately exit1; the outer runner succeeds only when the
   exact stage/SQL oracle/errno and absence of Snapshot/test admission agree.
5. Save results/events/logs, inputs and hashes before deleting reproducible
   caches/venvs/host binaries. Main adoption and release are separate decisions.

The sample's first revision creates users and inserts one legacy row. The second
adds a required rating column/default and an address table with foreign key and
unique email. Explicit seed adds a second user/address. Tests commit a third
user, then prove a distinct next child starts with the original two users and
still enforces the foreign key. Source/schema/revision/seed checks happen before
Snapshot. Failures are injected after the second revision's first DDL, or during
seed, with different missing-table statements. Partial DDL is observed, not
mistaken for an all-or-nothing migration guarantee.

## Copyable integration shape

For an application whose Alembic environment reads `sqlalchemy.url`:

```python
@pytest.fixture(scope="session")
def mariamem_prepare():
    def prepare(db):
        info = db.connection_info()
        # Explicitly create/select the application schema, if different from
        # the initial database, using info and close that bootstrap connection.
        url = sqlalchemy.URL.create(
            "mysql+pymysql", username=info["user"], password=info["password"],
            host=info["host"], port=info["port"], database="app",
        )
        config = alembic.config.Config("alembic.ini")
        config.set_main_option("sqlalchemy.url", url.render_as_string(
            hide_password=False).replace("%", "%%"))
        alembic.command.upgrade(config, "head")
        seed_with_explicit_settings(info, database="app")
        # Migration environment and seed must close/dispose their connections.
        # Callback return is ignored; returning a cleanup callable is not teardown.
    return prepare

@pytest.mark.shadow_maria
def test_create_user():
    application.create_user()

@pytest.mark.shadow_maria
def test_update_user():
    application.update_user()
```

Define the original application profile/driver and register its quiescent
SQLAlchemy engine as in the existing routing guide. Test connections use the
normal application URL; preparation uses the explicit source URL. This is not
preparation-time automatic routing. A custom env.py may read a different setting;
the recipe must match that entry instead of assuming Config.attributes is used.

First setup: original profile/engine registration, one preparation callback and
migration URL configuration. Second test: the same marker plus application test
body; no new DB preparation or manual cleanup SQL. These are recipe steps, not
measured usability/time or performance claims. Dump import remains separate.
