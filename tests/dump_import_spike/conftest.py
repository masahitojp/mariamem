"""Reuse stable fixture instrumentation/application; replace preparation only."""
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest

OWNER = Path(__file__).resolve().parents[1]/'preparation_migration_acceptance'
sys.path.insert(0, str(OWNER))
spec = importlib.util.spec_from_file_location('migration_fixture_owner', OWNER/'conftest.py')
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
mariamem_options = owner.mariamem_options
mariamem_server = owner.mariamem_server
mariamem_sqlalchemy_engines = owner.mariamem_sqlalchemy_engines

from observe import record
from oracles import check_expected, connect, differences, observe
from reader import ImportFailure
from routes import empty_schema, load


@pytest.fixture(scope='session')
def mariamem_prepare():
    def prepare(db):
        route, mode = os.environ['DUMP_ROUTE'], os.environ['DUMP_MODE']
        out = Path(os.environ['DUMP_OUTPUT'])
        record('prepare_start', route=route, mode=mode)
        info = db.connection_info()
        try:
            empty_schema(info)
            receipt = load(info, route, mode, json.loads(os.environ['DUMP_CLIENT']), out)
            (out/'import.json').write_text(json.dumps(receipt, indent=2)+'\n')
            with connect(info) as connection:
                observation = observe(connection)
                (out/'observations.json').write_text(json.dumps(observation, indent=2, ensure_ascii=False)+'\n')
                check_expected(observation)
                reference = json.loads(Path(os.environ['DUMP_REFERENCE']).read_text())
                assert reference['result'] == 'PASS'
                changed = differences(reference['observation'], observation)
                assert not changed, 'native reference differences: '+','.join(changed)
            record('prepared_state', reference_equal=True)
        except ImportFailure as error:
            partial = []
            with connect(info) as connection:
                with connection.cursor() as cursor:
                    cursor.execute('SHOW TABLES')
                    partial = [row[0] for row in cursor.fetchall()]
            record('partial_source_state', tables=partial)
            record('prepare_error', route=route, mode=mode,
                   **error.details,
                   original_exception=type(error.__cause__).__name__ if error.__cause__ else None,
                   next_action='Inspect the preserved original-file location against the native control; discard this source before retrying.')
            raise
        finally:
            record('preparation_connections_closed')
        db.wait_disconnected()
        record('preparation_disconnected', active_connections=db.status()['active_connections'])
    return prepare
