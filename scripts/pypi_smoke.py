#!/usr/bin/env python3
"""Run only in a fresh installed-wheel venv; no repository package imports."""
import hashlib
import json
from pathlib import Path
import platform
import sys


def check(version, expected_platform="darwin-arm64", expected_host_sha=None):
    import mariamem
    import pymysql

    expected = {"darwin-arm64": ("Darwin", "arm64"), "linux-x86_64": ("Linux", "x86_64"),
                "linux-aarch64": ("Linux", "aarch64")}.get(expected_platform)
    if expected is None or (platform.system(), platform.machine()) != expected:
        raise RuntimeError(f"expected native {expected_platform} smoke")
    if mariamem.__version__ != version:
        raise RuntimeError('installed package version differs')
    if not Path(mariamem.__file__).is_relative_to(Path(sys.prefix)):
        raise RuntimeError('package imported outside installed environment')
    if expected_host_sha is not None:
        native = Path(mariamem.__file__).parent / '_native'
        manifest = json.loads((native / 'manifest.json').read_text())
        actual = hashlib.sha256((native / 'mariamem-host').read_bytes()).hexdigest()
        if actual != expected_host_sha or manifest['sha256']['mariamem-host'] != actual:
            raise RuntimeError('installed host differs from accepted wheel')
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
    print(json.dumps(check(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'darwin-arm64', sys.argv[3] if len(sys.argv) > 3 else None)))
