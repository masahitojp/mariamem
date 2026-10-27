"""Own one disposable DB while an ordinary Django/pytest test process runs."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import mariamem


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', type=Path, required=True)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--settings', required=True)
    parser.add_argument('--runner', choices=['manage', 'pytest'], default='manage')
    parser.add_argument('--timeout', type=int, default=120)
    parser.add_argument('tests', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    tests = args.tests[1:] if args.tests[:1] == ['--'] else args.tests
    project = args.project.resolve()
    # Django owns its test database and per-test rollback/flush. The parent
    # owns the whole disposable server, including partial migration state.
    with mariamem.start(host_binary=args.host.resolve()) as source:
        info = source.connection_info()
        env = dict(os.environ, E2E_DB_HOST=info['host'], E2E_DB_PORT=str(info['port']),
                   E2E_DB_NAME=info['database'], DJANGO_SETTINGS_MODULE=args.settings,
                   PYTHONPATH=os.pathsep.join([str(Path(__file__).parent.resolve()),
                                               str(project), os.environ.get('PYTHONPATH', '')]))
        command = [sys.executable, str(project / 'manage.py'), 'test', '--noinput']
        if args.runner == 'pytest':
            command = [sys.executable, '-m', 'pytest']
        result = subprocess.run(command + tests, cwd=project, env=env, timeout=args.timeout)
    # Leave the original test-process exit code visible after server cleanup.
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
