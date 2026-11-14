#!/usr/bin/env python3
"""Short SQL/Close smoke; callers select and verify source host or installed wheel."""
import argparse
import json
import platform
import sysconfig


PLATFORMS = {"darwin-arm64": ("Darwin", "arm64"),
             "linux-x86_64": ("Linux", "x86_64"),
             "linux-aarch64": ("Linux", "aarch64")}


def native_platform():
    actual = (platform.system(), platform.machine())
    for name, identity in PLATFORMS.items():
        if actual == identity:
            return name
    raise RuntimeError(f"unsupported native smoke platform: {actual}")


def check(version, expected_platform="darwin-arm64", *, host=None):
    import mariamem
    import pymysql

    expected = PLATFORMS.get(expected_platform)
    windows = {'windows-x86_64': 'win-amd64', 'windows-arm64': 'win-arm64'}
    matches = ((platform.system() == 'Windows' and sysconfig.get_platform() == windows[expected_platform])
               if expected_platform in windows else expected is not None and (platform.system(), platform.machine()) == expected)
    if not matches:
        raise RuntimeError(f"expected native {expected_platform} smoke")
    if mariamem.__version__ != version:
        raise RuntimeError('installed package version differs')
    db = mariamem.start(**({"host_binary": host} if host is not None else {}))
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('version')
    parser.add_argument('platform', nargs='?', default='darwin-arm64')
    parser.add_argument('--host', help='explicit source host; wheel callers use bundled host')
    args = parser.parse_args()
    print(json.dumps(check(args.version, args.platform, host=args.host)))
