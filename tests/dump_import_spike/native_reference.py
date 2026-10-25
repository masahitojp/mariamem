"""Native import reference, with its own exact-input/failure observations."""
import argparse
import json
from pathlib import Path
import platform
import sys

from bind_input import check_binding
from linux_acquisition import source_identity

from oracles import check_expected, connect, enforce_constraints, observe
from reader import ImportFailure
from routes import CANONICAL_SHA256, empty_schema, load


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--client-command', required=True, help='JSON argv prefix')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-source-commit', required=True)
    parser.add_argument('--binding', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    info = dict(host='127.0.0.1', port=args.port, user='root', database='mysql')
    command = json.loads(args.client_command)
    source_identity(args.expected_source_commit)
    binding = check_binding(args.binding, args.expected_source_commit)
    report = {'result': 'FAIL', 'platform': platform.platform(), 'python': sys.version,
              'source_commit': args.expected_source_commit, 'binding': binding,
              'dump_sha256': CANONICAL_SHA256, 'route': 'native', 'runs': {}}
    try:
        for mode in ['success', 'sql_failure', 'malformed', 'source']:
            empty_schema(info, drop=True)
            scenario = {}
            report['runs'][mode] = scenario
            try:
                scenario['import'] = load(info, 'native', mode, command, args.output/mode)
                assert mode == 'success', 'negative input unexpectedly imported'
                with connect(info) as connection:
                    scenario['observation'] = observe(connection)
                    check_expected(scenario['observation'])
                    scenario['constraint_errors'] = enforce_constraints(connection)
            except ImportFailure as error:
                scenario['failure'] = error.details
                if mode == 'sql_failure':
                    assert error.details['errno'] == 1146 and error.details['sqlstate'] == '42S02'
                elif mode == 'malformed':
                    assert error.details['errno'] == 1064 and error.details['sqlstate'] == '42000'
                elif mode == 'source':
                    assert error.details['reason'] == 'sandbox_rejected_client_command'
                else:
                    raise
                with connect(info) as connection:
                    with connection.cursor() as cursor:
                        cursor.execute('SHOW TABLES')
                        scenario['partial_tables'] = [row[0] for row in cursor.fetchall()]
                        assert 'users' in scenario['partial_tables']
                        if mode == 'sql_failure':
                            assert 'spike_partial' in scenario['partial_tables']
            scenario['accepted'] = True
        report['observation'] = report['runs']['success']['observation']
        report['result'] = 'PASS'
    finally:
        (args.output/'reference.json').write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps({'result': report['result'], 'modes': list(report['runs'])}))


if __name__ == '__main__':
    main()
