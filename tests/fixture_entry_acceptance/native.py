"""Fresh MariaDB reference for P1's authored command/callback input, not Fork proof."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
INPUTS = [
    'tests/fixture_entry_acceptance/p1_migrate.py',
    'tests/preparation_migration_acceptance/application.py',
    'tests/preparation_migration_acceptance/migrations/env.py',
    'tests/preparation_migration_acceptance/migrations/versions/m1_initial.py',
    'tests/preparation_migration_acceptance/migrations/versions/m2_addresses.py',
]


def validate(observation):
    assert observation['version'].split('-')[0] == '12.3.3'
    assert observation['users'] == [[1, 'legacy', 0], [2, 'seed', 5]]
    assert observation['addresses'] == [[1, 2, 'seed@example.test']]
    assert observation['revision'] == [['m2_addresses']]
    assert observation['columns'] == [
        ['addresses', 'id', 'int', 'NO'], ['addresses', 'user_id', 'int', 'NO'],
        ['addresses', 'email', 'varchar', 'NO'], ['users', 'id', 'int', 'NO'],
        ['users', 'name', 'varchar', 'NO'], ['users', 'rating', 'int', 'NO']]
    assert observation['constraints'] == [
        ['addresses', 'FOREIGN KEY'], ['addresses', 'PRIMARY KEY'],
        ['addresses', 'UNIQUE'], ['users', 'PRIMARY KEY'], ['users', 'UNIQUE']]
    assert observation['foreign_key_errno'] == 1452
    assert observation['subsequent_select'] == 1
    assert observation['distinct_physical_connections'] == 2
    assert observation['pool_checkedout_after'] == 0
    assert [row[0] for row in observation['tables']] == ['addresses', 'alembic_version', 'users']
    assert all(row[1] == 'InnoDB' and row[2] for row in observation['tables'])


def observe(engine):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError
    def rows(sql):
        with engine.connect() as connection:
            return [list(row) for row in connection.execute(text(sql))]
    value = dict(
        version=rows('SELECT VERSION()')[0][0],
        users=rows('SELECT id,name,rating FROM users ORDER BY id'),
        addresses=rows('SELECT id,user_id,email FROM addresses ORDER BY id'),
        revision=rows('SELECT version_num FROM alembic_version'),
        columns=rows("SELECT table_name,column_name,data_type,is_nullable FROM information_schema.columns "
                     "WHERE table_schema='app' AND table_name IN ('users','addresses') "
                     'ORDER BY table_name,ordinal_position'),
        constraints=rows("SELECT table_name,constraint_type FROM information_schema.table_constraints "
                         "WHERE table_schema='app' AND table_name IN ('users','addresses') "
                         'ORDER BY table_name,constraint_type'),
        tables=rows("SELECT table_name,engine,table_collation FROM information_schema.tables "
                    "WHERE table_schema='app' ORDER BY table_name"))
    try:
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO addresses VALUES(2,9999,'invalid@example.test')"))
    except IntegrityError as error:
        value['foreign_key_errno'] = error.orig.args[0]
    else:
        raise AssertionError('native reference accepted invalid foreign key')
    with engine.connect() as first, engine.connect() as second:
        value['distinct_physical_connections'] = len({
            first.execute(text('SELECT CONNECTION_ID()')).scalar_one(),
            second.execute(text('SELECT CONNECTION_ID()')).scalar_one()})
        value['subsequent_select'] = second.execute(text('SELECT 1')).scalar_one()
    value['pool_checkedout_after'] = engine.pool.checkedout()
    validate(value)
    return value


def validate_reference(receipt, source_commit, python_minor):
    assert receipt['result'] == 'PASS_P1_NATIVE_INPUT'
    assert receipt['source_commit'] == source_commit
    assert receipt['python'].startswith(python_minor + '.')
    assert receipt['schema_count_after'] == 0
    assert set(receipt['runs']) == {'command', 'callback'}
    for value in receipt['runs'].values():
        validate(value)
    assert receipt['runs']['command'] == receipt['runs']['callback']
    assert receipt['inputs_sha256'] == {
        name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in INPUTS}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--expected-source-commit', required=True)
    parser.add_argument('--acquisition', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--disposable-server', action='store_true', required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT/'scripts'))
    from git_identity import require_commit
    identity = require_commit(ROOT, args.expected_source_commit)
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == identity.source_commit
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()
    acquisition = json.loads((args.acquisition/'result.json').read_text())
    assert acquisition['result'] == 'PASS' and acquisition['source_commit'] == identity.source_commit
    args.output.mkdir(parents=True, exist_ok=False)
    receipt = dict(result='FAIL', source_commit=identity.source_commit,
                   scope='P1 native input and command component; no Snapshot/Fork or resource acceptance',
                   python=sys.version, platform=platform.platform(),
                   acquisition_sha256=hashlib.sha256((args.acquisition/'observed.json').read_bytes()).hexdigest(),
                   inputs_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in INPUTS},
                   packages={name:importlib.metadata.version(name) for name in ['Alembic','SQLAlchemy','PyMySQL']},
                   runs={})
    from sqlalchemy import URL, create_engine, text
    from mariamem import PrepareCommand
    from mariamem._prepare import _run_command
    from p1_migrate import prepare
    info = dict(host='127.0.0.1', port=args.port, user='root', password='', database='mysql')
    class NativeTarget:
        def connection_info(self):
            return info.copy()
    url = URL.create('mysql+pymysql', username='root', password='', host='127.0.0.1', port=args.port, database='mysql')
    admin = create_engine(url, pool_size=1, max_overflow=0)
    migrations = ROOT/'tests/preparation_migration_acceptance/migrations'
    owned = False
    before_env = os.environ.copy()
    try:
        with admin.connect() as connection:
            assert connection.execute(text('SELECT VERSION()')).scalar_one().split('-')[0] == '12.3.3'
            assert connection.execute(text("SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name='app'")).scalar_one() == 0, 'refuse pre-existing app schema'
        os.environ.update(P1_EVENT_FILE=str((args.output/'events.jsonl').resolve()), P1_MIGRATION_SOURCE=str(migrations))
        for method in ('command', 'callback'):
            # This schema belongs exclusively to this disposable-service campaign.
            owned = True
            if method == 'command':
                result = _run_command(PrepareCommand([sys.executable, str(ROOT/INPUTS[0])]), NativeTarget(), ROOT)
                assert result.process_cleanup == 'completed' and result.returncode == 0
                for stream in ('stdout', 'stderr'):
                    (args.output/(stream+'.txt')).write_bytes(getattr(result, stream))
            else:
                prepare(info, migrations)
            engine = create_engine(url.set(database='app'), pool_size=1, max_overflow=1)
            try:
                receipt['runs'][method] = observe(engine)
            finally:
                engine.dispose()
            with admin.begin() as connection:
                connection.execute(text('DROP DATABASE app'))
            owned = False
        assert receipt['runs']['command'] == receipt['runs']['callback']
        receipt['result'] = 'PASS_P1_NATIVE_INPUT'
    finally:
        try:
            with admin.begin() as connection:
                if owned:
                    connection.execute(text('DROP DATABASE IF EXISTS app'))
                receipt['schema_count_after'] = connection.execute(text("SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name='app'")).scalar_one()
                assert receipt['schema_count_after'] == 0
        except BaseException:
            receipt['result'] = 'FAIL'
            raise
        finally:
            admin.dispose()
            os.environ.clear()
            os.environ.update(before_env)
            (args.output/'result.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
