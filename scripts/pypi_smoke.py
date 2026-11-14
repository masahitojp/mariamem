#!/usr/bin/env python3
"""Run only in a fresh installed-wheel venv; no repository package imports."""
import json
import platform
import sys
import sysconfig


def check(version, expected_platform="darwin-arm64"):
    import mariamem
    import pymysql

    expected = {"darwin-arm64": ("Darwin", "arm64"), "linux-x86_64": ("Linux", "x86_64"),
                "linux-aarch64": ("Linux", "aarch64")}.get(expected_platform)
    windows = {'windows-x86_64': 'win-amd64', 'windows-arm64': 'win-arm64'}
    matches = ((platform.system() == 'Windows' and sysconfig.get_platform() == windows[expected_platform])
               if expected_platform in windows else expected is not None and (platform.system(), platform.machine()) == expected)
    if not matches:
        raise RuntimeError(f"expected native {expected_platform} smoke")
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
            'os': platform.mac_ver()[0] if platform.system() == 'Darwin' else platform.release(), 'machine': platform.machine(), 'host_exit': process.returncode}


if __name__ == '__main__':
    print(json.dumps(check(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'darwin-arm64')))
