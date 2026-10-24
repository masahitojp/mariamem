"""Acceptance observations around the unchanged public fixture chain."""
import os
from pathlib import Path

import pytest
import mariamem


from observe import record


@pytest.fixture(scope='session')
def mariamem_options():
    return {'host_binary': os.environ['MIGRATION_HOST']}


@pytest.fixture(scope='session')
def mariamem_server(mariamem_options):
    db = None
    try:
        with mariamem.start(**mariamem_options) as db:
            record('source_start', id=db.id, **db.diagnostics)
            capture = db.snapshot
            def snapshot(*args, **options):
                record('snapshot_attempt')
                result = capture(*args, **options)
                record('snapshot_success')
                return result
            db.snapshot = snapshot
            yield db
    finally:
        if db is not None:
            # Private state is read only for acceptance cleanup diagnostics.
            record('source_cleanup', closed=db.closed,
                   host_reaped=db._session._process.poll() is not None,
                   directory_removed=not db._session.root.exists())


@pytest.fixture(scope='session')
def mariamem_sqlalchemy_engines():
    from application import engine
    return (engine,)


@pytest.fixture(scope='session')
def mariamem_prepare():
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import URL, create_engine, inspect, text
    from mariamem.routing import RoutingError
    import application

    def prepare(db):
        record('prepare_start')
        info = db.connection_info()
        def engine_for(schema):
            return create_engine(URL.create('mysql+pymysql', username=info['user'],
                password=info['password'], host=info['host'], port=info['port'], database=schema))
        bootstrap, target = engine_for(info['database']), engine_for('app')
        stage = 'schema'
        try:
            # This is an oracle, not preparation routing. The original profile
            # must still refuse while no test binding exists.
            with pytest.raises(RoutingError, match='missing_target'):
                application.users()
            record('preparation_original_profile_refused')
            with bootstrap.begin() as connection:
                connection.execute(text('CREATE DATABASE app'))
            config = Config()
            config.set_main_option('script_location', str(Path(__file__).parent / 'migrations'))
            config.set_main_option('sqlalchemy.url', target.url.render_as_string(hide_password=False).replace('%', '%%'))
            config.attributes['fail_revision'] = os.environ['MIGRATION_MODE'] == 'revision_failure'
            stage = 'migration'
            command.upgrade(config, 'head')
            record('migration_complete')
            stage = 'seed'
            with target.begin() as connection:
                connection.execute(text("INSERT INTO users(id,name,rating) VALUES(2,'seed',5)"))
                if os.environ['MIGRATION_MODE'] == 'seed_failure':
                    connection.execute(text('INSERT INTO missing_seed_oracle(id) VALUES(1)'))
                connection.execute(text("INSERT INTO addresses(id,user_id,email) VALUES(1,2,'seed@example.test')"))
            stage = 'verification'
            with target.connect() as connection:
                revision = connection.scalar(text('SELECT version_num FROM alembic_version'))
                rows = [list(row) for row in connection.execute(text('SELECT id,name,rating FROM users ORDER BY id'))]
                addresses = [list(row) for row in connection.execute(text('SELECT id,user_id,email FROM addresses'))]
            metadata = inspect(target)
            columns = {c['name']: c for c in metadata.get_columns('users')}
            foreign_keys = metadata.get_foreign_keys('addresses')
            assert revision == 'm2_addresses'
            assert rows == [[1,'legacy',0], [2,'seed',5]]
            assert addresses == [[1,2,'seed@example.test']]
            assert columns['rating']['nullable'] is False
            assert any(f['referred_table']=='users' and f['constrained_columns']==['user_id'] for f in foreign_keys)
            assert any(u['column_names']==['name'] for u in metadata.get_unique_constraints('users'))
            record('prepared_state', revision=revision, rows=rows, addresses=addresses,
                   columns=sorted(columns), foreign_key_verified=True, unique_verified=True)
        except BaseException as error:
            original = getattr(error, 'orig', error)
            statement = getattr(error, 'statement', None)
            oracle = {'INSERT INTO missing_revision_oracle(id) VALUES(1)': 'revision_failure',
                      'INSERT INTO missing_seed_oracle(id) VALUES(1)': 'seed_failure'}.get(statement)
            record('prepare_error', stage=stage, oracle=oracle, exception=type(error).__name__,
                   original_exception=type(original).__name__,
                   errno=original.args[0] if original.args and isinstance(original.args[0], int) else None)
            try:
                metadata = inspect(target)
                with target.connect() as connection:
                    revision = connection.scalar(text('SELECT version_num FROM alembic_version'))
                record('partial_source_state', tables=metadata.get_table_names(),
                       columns=[c['name'] for c in metadata.get_columns('users')], revision=revision)
            except Exception as diagnostic:
                record('partial_state_unavailable', exception=type(diagnostic).__name__)
            raise
        finally:
            bootstrap.dispose()
            target.dispose()
            record('preparation_engines_disposed')
        db.wait_disconnected()
        record('preparation_disconnected', active_connections=db.status()['active_connections'])
    return prepare
