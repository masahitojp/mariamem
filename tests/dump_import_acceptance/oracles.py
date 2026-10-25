"""Fixed observation projection: no dump or SQL normalization."""
from decimal import Decimal
import json

import pymysql
from pathlib import Path

_INPUT = json.loads((Path(__file__).parent/'input/input-manifest.json').read_text())
MODE = _INPUT['sql_mode']
VALUES = _INPUT['extension_values_decimal_strings_binary_hex']

INIT = ("SET time_zone='+00:00', sql_mode='"+MODE+"', "
        "collation_connection='utf8mb4_unicode_ci', foreign_key_checks=1, "
        "unique_checks=1, sql_notes=1, autocommit=1, note_verbosity=3")
SESSION = ('@@time_zone', '@@sql_mode', '@@character_set_client', '@@character_set_results',
           '@@collation_connection', '@@foreign_key_checks', '@@unique_checks',
           '@@sql_notes', '@@autocommit', '@@note_verbosity')
PROJECTIONS = {
    'tables': "SELECT TABLE_NAME, ENGINE, TABLE_COLLATION, AUTO_INCREMENT FROM information_schema.tables WHERE TABLE_SCHEMA='app' ORDER BY TABLE_NAME",
    'columns': "SELECT TABLE_NAME, COLUMN_NAME, ORDINAL_POSITION, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, EXTRA, CHARACTER_SET_NAME, COLLATION_NAME FROM information_schema.columns WHERE TABLE_SCHEMA='app' ORDER BY TABLE_NAME, ORDINAL_POSITION",
    'constraints': "SELECT TABLE_NAME, CONSTRAINT_NAME, CONSTRAINT_TYPE FROM information_schema.table_constraints WHERE TABLE_SCHEMA='app' ORDER BY TABLE_NAME, CONSTRAINT_NAME",
    'key_columns': "SELECT TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME FROM information_schema.key_column_usage WHERE TABLE_SCHEMA='app' ORDER BY TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION",
    'references': "SELECT TABLE_NAME, CONSTRAINT_NAME, REFERENCED_TABLE_NAME, UPDATE_RULE, DELETE_RULE FROM information_schema.referential_constraints WHERE CONSTRAINT_SCHEMA='app' ORDER BY TABLE_NAME, CONSTRAINT_NAME",
    'indexes': "SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX, COLUMN_NAME, SUB_PART, INDEX_TYPE, COLLATION FROM information_schema.statistics WHERE TABLE_SCHEMA='app' ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX",
    'routines': "SELECT ROUTINE_NAME, ROUTINE_TYPE, DTD_IDENTIFIER, ROUTINE_DEFINITION, IS_DETERMINISTIC, SQL_DATA_ACCESS, SECURITY_TYPE, SQL_MODE, DEFINER, CHARACTER_SET_CLIENT, COLLATION_CONNECTION, DATABASE_COLLATION FROM information_schema.routines WHERE ROUTINE_SCHEMA='app' ORDER BY ROUTINE_NAME",
    'parameters': "SELECT SPECIFIC_NAME, ORDINAL_POSITION, PARAMETER_MODE, PARAMETER_NAME, DTD_IDENTIFIER FROM information_schema.parameters WHERE SPECIFIC_SCHEMA='app' ORDER BY SPECIFIC_NAME, ORDINAL_POSITION",
    'users': 'SELECT id,name,rating FROM app.users ORDER BY id',
    'addresses': 'SELECT id,user_id,email FROM app.addresses ORDER BY id',
    'revision': 'SELECT version_num FROM app.alembic_version',
    'values': 'SELECT id,user_id,exact_value,note,payload FROM app.user_import_values ORDER BY id',
    'views': "SELECT TABLE_NAME FROM information_schema.views WHERE TABLE_SCHEMA='app'",
    'triggers': "SELECT TRIGGER_NAME FROM information_schema.triggers WHERE TRIGGER_SCHEMA='app'",
}


def value(obj):
    if isinstance(obj, Decimal):
        return {'decimal': str(obj)}
    if isinstance(obj, bytes):
        return {'binary_hex': obj.hex()}
    if isinstance(obj, (tuple, list)):
        return [value(v) for v in obj]
    return obj


def connect(info, schema='app'):
    return pymysql.connect(host=info['host'], port=info['port'], user=info['user'],
        password=info.get('password', ''), database=schema, charset='utf8mb4',
        autocommit=True, init_command=INIT, connect_timeout=10, read_timeout=60)


def session(connection):
    with connection.cursor() as cursor:
        cursor.execute('SELECT '+','.join(SESSION))
        row = list(cursor.fetchone())
        row[1] = sorted(row[1].split(','))
        return row


def observe(connection):
    result = {}
    with connection.cursor() as cursor:
        for name, sql in PROJECTIONS.items():
            cursor.execute(sql)
            result[name] = value(cursor.fetchall())
        # SQL_MODE is compared as a set of flags, all other definition fields exact.
        for routine in result['routines']:
            routine[7] = sorted(routine[7].split(','))
        result['procedure_results'] = []
        for user_id in [1, 2]:
            cursor.execute('CALL app.app_user_values(%s)', (user_id,))
            sets = [value(cursor.fetchall())]
            while cursor.nextset():
                sets.append(value(cursor.fetchall()))
            result['procedure_results'].append(sets)
        cursor.execute('SELECT app.app_user_rating(1,3), app.app_user_rating(2,-2)')
        result['function_results'] = value(cursor.fetchall())
        cursor.execute('SELECT 123 AS subsequent_select')
        result['subsequent_select'] = value(cursor.fetchall())
    return result


def check_expected(observation):
    assert observation['users'] == [[1, 'legacy', 0], [2, 'seed', 5]]
    assert observation['addresses'] == [[1, 2, 'seed@example.test']]
    assert observation['revision'] == [['m2_addresses']]
    expected = [[i, user, {'decimal': decimal}, note,
                 {'binary_hex': payload} if payload is not None else None]
                for i, user, decimal, note, payload in VALUES]
    assert observation['values'] == expected
    assert observation['function_results'] == [[3, 3]]
    assert observation['subsequent_select'] == [[123]]
    assert observation['views'] == observation['triggers'] == []
    for routine in observation['routines']:
        assert routine[6] == 'DEFINER' and routine[8] == 'root@localhost'
    assert len(observation['routines']) == 2
    for user_id, sets in zip([1, 2], observation['procedure_results']):
        assert sets == [[row for row in expected if row[1] == user_id], [[user_id]], []]


def enforce_constraints(connection):
    errors = []
    with connection.cursor() as cursor:
        for sql, expected in [
            ("INSERT INTO app.addresses(id,user_id,email) VALUES(9,9999,'invalid@example.test')", 1452),
            ("INSERT INTO app.users(id,name,rating) VALUES(9,'seed',0)", 1062)]:
            try:
                cursor.execute(sql)
            except pymysql.Error as failure:
                assert failure.args[0] == expected
                errors.append(expected)
            else:
                raise AssertionError('constraint not enforced')
    return errors


def differences(expected, actual):
    return [key for key in expected if expected[key] != actual.get(key)]
