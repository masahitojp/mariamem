"""Produce one identified real dump of the existing migration app + extension."""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess

import pymysql
from alembic import command
from alembic.config import Config
from sqlalchemy import URL

MODE = 'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'
EXTENSION = [
    '''CREATE TABLE user_import_values (
        id INT NOT NULL PRIMARY KEY, user_id INT NOT NULL,
        exact_value DECIMAL(20,6) NOT NULL, note LONGTEXT NULL,
        payload VARBINARY(32) NULL,
        CONSTRAINT fk_import_user FOREIGN KEY(user_id) REFERENCES users(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci''',
    '''CREATE DEFINER='root'@'localhost' PROCEDURE app_user_values(IN requested_user INT)
       READS SQL DATA SQL SECURITY DEFINER
       BEGIN
         SELECT id,user_id,exact_value,note,payload FROM user_import_values
           WHERE user_id=requested_user ORDER BY id;
         SELECT requested_user AS selected_user;
       END''',
    '''CREATE DEFINER='root'@'localhost' FUNCTION app_user_rating(requested_user INT, delta INT)
       RETURNS INT DETERMINISTIC READS SQL DATA SQL SECURITY DEFINER
       BEGIN
         DECLARE current_rating INT;
         SELECT rating INTO current_rating FROM users WHERE id=requested_user;
         RETURN current_rating + delta;
       END''',
]
VALUES = [
    [1, 1, '12345678901234.123456', None, None],
    [2, 2, '-1.000001', '', ''],
    [3, 2, '0.100000', '日本語🙂 \'quoted\' "double" \\ path; newline\nend', '00273b5cff'],
    [4, 1, '0.000000', "backslash\\semicolon;quote'", '00'],
]
OPTIONS = ['--no-defaults', '--protocol=tcp', '--host=127.0.0.1', '--port=3306',
           '--user=root', '--opt', '--single-transaction', '--skip-lock-tables',
           '--skip-add-locks', '--routines', '--triggers', '--skip-events', '--hex-blob',
           '--default-character-set=utf8mb4', '--tz-utc', '--order-by-primary',
           '--skip-dump-date', 'app']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--container', required=True)
    parser.add_argument('--port', type=int, default=3307)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[2]
    owner = root/'tests/preparation_migration_acceptance'
    manifest = {
        'schema': 1, 'fixture_origin': 'existing repository-authored migration application, extended',
        'source_commit': json.loads(subprocess.check_output(
            ['python3', 'scripts/git_identity.py', 'inspect', 'HEAD'], cwd=root, text=True))['source_commit'],
        'migration_owner': {str(p.relative_to(root)): sha(p) for p in sorted(owner.rglob('*.py'))},
        'base_users': [[1, 'legacy', 0], [2, 'seed', 5]],
        'base_addresses': [[1, 2, 'seed@example.test']], 'revision': 'm2_addresses',
        'extension_sql': EXTENSION, 'extension_values_decimal_strings_binary_hex': VALUES,
        'producer_options': OPTIONS,
        'excluded': ['views', 'triggers', 'events', 'packages', 'MySQL dumps', 'external legacy apps'],
        'sql_mode': MODE, 'timezone': '+00:00', 'charset': 'utf8mb4',
        'collation': 'utf8mb4_unicode_ci', 'definer': 'root@localhost',
        'sql_security': 'DEFINER', 'result': 'PENDING',
    }
    # Save expected inputs before creating or dumping them.
    (out/'input-manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n')
    connection = pymysql.connect(host='127.0.0.1', port=args.port, user='root',
                                  charset='utf8mb4', autocommit=True)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT VERSION(), @@version_compile_machine')
            manifest['server'] = cursor.fetchone()
            assert manifest['server'][0].startswith('12.3.3')
            assert manifest['server'][1] == 'x86_64'
            cursor.execute("SELECT user,host FROM mysql.user WHERE user='root' AND host='localhost'")
            assert cursor.fetchall() == (('root', 'localhost'),)
            cursor.execute('CREATE DATABASE app CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
        config = Config()
        config.set_main_option('script_location', str(owner/'migrations'))
        url = URL.create('mysql+pymysql', username='root', host='127.0.0.1',
            port=args.port, database='app', query={'charset': 'utf8mb4',
            'init_command': "SET time_zone='+00:00', sql_mode='"+MODE+"'"})
        config.set_main_option('sqlalchemy.url', url.render_as_string(hide_password=False).replace('%', '%%'))
        command.upgrade(config, 'head')
        connection.select_db('app')
        with connection.cursor() as cursor:
            cursor.execute("SET time_zone='+00:00', sql_mode=%s", (MODE,))
            cursor.execute("INSERT INTO users(id,name,rating) VALUES(2,'seed',5)")
            cursor.execute("INSERT INTO addresses(id,user_id,email) VALUES(1,2,'seed@example.test')")
            cursor.execute('SELECT id,name,rating FROM users ORDER BY id')
            assert list(map(list, cursor.fetchall())) == manifest['base_users']
            cursor.execute('SELECT id,user_id,email FROM addresses ORDER BY id')
            assert list(map(list, cursor.fetchall())) == manifest['base_addresses']
            cursor.execute('SELECT version_num FROM alembic_version')
            assert cursor.fetchone() == ('m2_addresses',)
            for statement in EXTENSION:
                cursor.execute(statement)
            cursor.executemany('INSERT INTO user_import_values VALUES(%s,%s,%s,%s,%s)',
                [(i, user, Decimal(value), note, bytes.fromhex(payload) if payload is not None else None)
                 for i, user, value, note, payload in VALUES])
            cursor.execute("SELECT COUNT(*) FROM information_schema.triggers WHERE trigger_schema='app'")
            assert cursor.fetchone() == (0,)
            cursor.execute("SELECT COUNT(*) FROM information_schema.views WHERE table_schema='app'")
            assert cursor.fetchone() == (0,)
        argv = ['docker', 'exec', args.container, 'mariadb-dump', *OPTIONS]
        manifest['dump_argv'] = argv
        with (out/'application.sql').open('xb') as dump, (out/'producer.stderr.txt').open('wb') as log:
            subprocess.run(argv, stdout=dump, stderr=log, check=True, timeout=60)
        manifest['dump_sha256'] = sha(out/'application.sql')
        manifest['result'] = 'PASS'
    finally:
        connection.close()
        (out/'input-manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n')


if __name__ == '__main__':
    main()
