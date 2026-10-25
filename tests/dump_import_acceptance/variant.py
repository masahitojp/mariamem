"""Fresh same-profile data variant: native production and native round trip."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from linux_acquisition import source_identity
from oracles import connect, observe, enforce_constraints
from producer import OPTIONS
from routes import CANONICAL_SHA256, empty_schema, native_import


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--container', required=True)
    parser.add_argument('--expected-source-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source_identity(args.expected_source_commit)
    args.output.mkdir(parents=True)
    info = dict(host='127.0.0.1', port=3307, user='root', database='mysql')
    # Native-reference's final scenario leaves the original application's rows.
    # Keep the same tables, constraints and routines; vary actual literal values.
    mutations = [
        ("UPDATE app.users SET name=%s,rating=%s WHERE id=1", ["別の 'user'; \\ path", 17]),
        ("UPDATE app.user_import_values SET note=%s,exact_value=%s WHERE id=3",
         ["DELIMITER ;;\nSOURCE ignored.sql; /* literal */ 🙂", '-123.456789']),
    ]
    with connect(info) as connection:
        with connection.cursor() as cursor:
            for sql, values in mutations:
                cursor.execute(sql, values)
            cursor.execute("UPDATE app.user_import_values SET payload=0xFF000A3B5C27 WHERE id=3")
        before = observe(connection)
    argv = ['docker', 'exec', args.container, 'mariadb-dump', *OPTIONS]
    with (args.output/'application.sql').open('xb') as out, (args.output/'producer.stderr.txt').open('wb') as err:
        subprocess.run(argv, stdout=out, stderr=err, check=True, timeout=60)
    raw = (args.output/'application.sql').read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert digest != CANONICAL_SHA256
    empty_schema(info, drop=True)
    command = ['docker', 'exec', '-i', args.container, 'mariadb']
    native_info = dict(info, port=3306)
    native_import(native_info, raw, command, args.output/'native')
    with connect(info) as connection:
        after = observe(connection)
        assert before == after
        constraints = enforce_constraints(connection)
    report = dict(result='PASS', source_commit=args.expected_source_commit,
                  dump_sha256=digest, dump_argv=argv, mutations=mutations,
                  binary_mutation='FF000A3B5C27', observation=after,
                  constraint_errors=constraints, native_roundtrip_equal=True)
    (args.output/'reference.json').write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n')


if __name__ == '__main__':
    main()
