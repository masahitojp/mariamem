#!/usr/bin/env python3
"""Run only in a fresh installed-wheel venv; no repository package imports."""
import json
import platform
import sys


def check(version):
    import mariamem
    import pymysql

    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise RuntimeError('expected native macOS arm64 smoke')
    if mariamem.__version__ != version:
        raise RuntimeError('installed package version differs')
    db = mariamem.start()
    process = db._session._process  # Observe the shipped host, including actual exit after Close.
    try:
        with pymysql.connect(**db.connection_info(), connect_timeout=10, read_timeout=10) as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                if cursor.fetchone() != (1,):
                    raise RuntimeError('SELECT 1 result differs')
    finally:
        db.close()
    if not db.closed or process.poll() != 0:
        raise RuntimeError('Close did not finish with successful host exit')
    return {'result': 'PASS', 'version': version, 'python': platform.python_version(),
            'os': platform.mac_ver()[0], 'machine': platform.machine(), 'host_exit': process.returncode}


if __name__ == '__main__':
    print(json.dumps(check(sys.argv[1])))
